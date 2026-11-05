import logging
import math
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

import httpx

from app.exceptions.base import FuentesNoDisponiblesError

logger = logging.getLogger(__name__)

CABECERA_RESET = "X-RateLimit-Reset"
ESTADO_LIMITE = 429
ESTADO_ERROR_SERVIDOR = 500


@dataclass(frozen=True)
class PoliticaReintento:
    """Un solo reintento: ante 429 solo si el reinicio del límite es corto; ante 5xx siempre."""

    espera_maxima_429: float
    espera_5xx: float
    dormir: Callable[[float], None] = time.sleep


@contextmanager
def turno(semaforo: threading.BoundedSemaphore, espera: float, proveedor: str) -> Iterator[None]:
    """Limita la concurrencia hacia un proveedor; si no hay turno a tiempo, se degrada."""
    if not semaforo.acquire(timeout=espera):
        logger.warning("fuentes_error proveedor=%s tipo=SinTurno estado=None reset=None", proveedor)
        raise FuentesNoDisponiblesError()
    try:
        yield
    finally:
        semaforo.release()


def crear_cliente_http(user_agent: str, timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": user_agent}, follow_redirects=True)


def _reset(respuesta: httpx.Response) -> float | None:
    try:
        valor = float(respuesta.headers.get(CABECERA_RESET, ""))
    except ValueError:
        return None
    return valor if math.isfinite(valor) and valor >= 0 else None


def _registrar_error(proveedor: str, tipo: str, respuesta: httpx.Response | None = None) -> None:
    """Solo proveedor, tipo, código HTTP y reinicio del límite: nunca URL, cabeceras ni cuerpo
    (la URL o las cabeceras pueden llevar credenciales)."""
    estado = respuesta.status_code if respuesta is not None else None
    # Solo el número ya interpretado: el texto crudo de la cabecera no se copia al log.
    reset = _reset(respuesta) if respuesta is not None else None
    logger.warning(
        "fuentes_error proveedor=%s tipo=%s estado=%s reset=%s", proveedor, tipo, estado, reset
    )


def _espera_reintento(respuesta: httpx.Response, politica: PoliticaReintento) -> float | None:
    if respuesta.status_code == ESTADO_LIMITE:
        reset = _reset(respuesta)
        # Sin cabecera o con reinicio largo (presupuesto diario agotado): no se reintenta.
        return reset if reset is not None and reset <= politica.espera_maxima_429 else None
    if respuesta.status_code >= ESTADO_ERROR_SERVIDOR:
        return politica.espera_5xx
    return None


def _error_de_estado(respuesta: httpx.Response) -> FuentesNoDisponiblesError:
    reset = _reset(respuesta) if respuesta.status_code == ESTADO_LIMITE else None
    cabeceras = {"Retry-After": str(max(1, math.ceil(reset)))} if reset is not None else None
    return FuentesNoDisponiblesError(cabeceras=cabeceras)


def obtener_json(
    cliente: httpx.Client,
    url: str,
    parametros: dict[str, Any],
    proveedor: str,
    cabeceras: dict[str, str] | None = None,
    politica: PoliticaReintento | None = None,
) -> Any:
    """Frontera de red de los adaptadores de fuentes: todo error se traduce a uno propio."""
    intentos = 2 if politica else 1
    for intento in range(1, intentos + 1):
        try:
            respuesta = cliente.get(url, params=parametros, headers=cabeceras)
        except httpx.HTTPError as exc:
            _registrar_error(proveedor, type(exc).__name__)
            raise FuentesNoDisponiblesError() from None
        if respuesta.is_success:
            try:
                return respuesta.json()
            except ValueError:
                _registrar_error(proveedor, "JSONInvalido", respuesta)
                raise FuentesNoDisponiblesError() from None
        espera = _espera_reintento(respuesta, politica) if politica else None
        _registrar_error(proveedor, "HTTPStatusError", respuesta)
        if politica is None or espera is None or intento == intentos:
            raise _error_de_estado(respuesta)
        politica.dormir(espera)
    raise FuentesNoDisponiblesError()  # pragma: no cover (el bucle siempre retorna o lanza)


# Sin DTD no hay expansión de entidades (XXE ni "billion laughs"): se rechaza antes de parsear.
MARCAS_DTD = (b"<!DOCTYPE", b"<!ENTITY")


def obtener_xml(
    cliente: httpx.Client, url: str, parametros: dict[str, Any], proveedor: str
) -> ElementTree.Element:
    """Igual que `obtener_json`, para APIs que solo responden XML."""
    respuesta: httpx.Response | None = None
    try:
        respuesta = cliente.get(url, params=parametros)
        respuesta.raise_for_status()
        if any(marca in respuesta.content for marca in MARCAS_DTD):
            raise ValueError("XML con DTD no permitido")
        return ElementTree.fromstring(respuesta.content)
    except (httpx.HTTPError, ValueError, ElementTree.ParseError) as exc:
        _registrar_error(proveedor, type(exc).__name__, respuesta)
        raise FuentesNoDisponiblesError() from exc
