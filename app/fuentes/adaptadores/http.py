import logging
from typing import Any
from xml.etree import ElementTree

import httpx

from app.exceptions.base import FuentesNoDisponiblesError

logger = logging.getLogger(__name__)


def crear_cliente_http(user_agent: str, timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": user_agent}, follow_redirects=True)


def obtener_json(
    cliente: httpx.Client, url: str, parametros: dict[str, Any], proveedor: str
) -> Any:
    """Frontera de red de los adaptadores de fuentes: todo error se traduce a uno propio."""
    try:
        respuesta = cliente.get(url, params=parametros)
        respuesta.raise_for_status()
        return respuesta.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("fuentes_error proveedor=%s tipo=%s", proveedor, type(exc).__name__)
        raise FuentesNoDisponiblesError() from exc


# Sin DTD no hay expansión de entidades (XXE ni "billion laughs"): se rechaza antes de parsear.
MARCAS_DTD = (b"<!DOCTYPE", b"<!ENTITY")


def obtener_xml(
    cliente: httpx.Client, url: str, parametros: dict[str, Any], proveedor: str
) -> ElementTree.Element:
    """Igual que `obtener_json`, para APIs que solo responden XML."""
    try:
        respuesta = cliente.get(url, params=parametros)
        respuesta.raise_for_status()
        if any(marca in respuesta.content for marca in MARCAS_DTD):
            raise ValueError("XML con DTD no permitido")
        return ElementTree.fromstring(respuesta.content)
    except (httpx.HTTPError, ValueError, ElementTree.ParseError) as exc:
        logger.warning("fuentes_error proveedor=%s tipo=%s", proveedor, type(exc).__name__)
        raise FuentesNoDisponiblesError() from exc
