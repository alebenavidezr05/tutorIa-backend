"""Descarga de imágenes externas con defensas contra SSRF, tipos falsos y tamaños excesivos."""

import ipaddress
import logging
import socket
from collections.abc import Callable
from urllib.parse import urljoin, urlsplit

import filetype
import httpx

from app.core.config import Settings
from app.exceptions.base import ArchivoInvalidoError, ImagenesNoDisponiblesError
from app.imagenes.base import DescargadorImagenes, ImagenProcesada, ProcesadorImagenes

logger = logging.getLogger(__name__)

ESQUEMA_PERMITIDO = "https"
MIMES_RASTER = {"image/jpeg", "image/png", "image/webp"}
CODIGOS_REDIRECCION = {301, 302, 303, 307, 308}
TAMANO_BLOQUE = 64 * 1024
Resolver = Callable[[str], list[str]]


def resolver_dns(host: str) -> list[str]:
    return [str(info[4][0]) for info in socket.getaddrinfo(host, None)]


def _es_ip_publica(ip: str) -> bool:
    direccion = ipaddress.ip_address(ip)
    return not (
        direccion.is_private
        or direccion.is_loopback
        or direccion.is_link_local
        or direccion.is_multicast
        or direccion.is_reserved
        or direccion.is_unspecified
    )


def _dominio_permitido(host: str, dominios: list[str]) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in dominios)


class DescargadorSeguro(DescargadorImagenes):
    def __init__(
        self,
        settings: Settings,
        procesador: ProcesadorImagenes,
        cliente: httpx.Client | None = None,
        resolver: Resolver = resolver_dns,
    ) -> None:
        self._settings = settings
        self._procesador = procesador
        self._resolver = resolver
        self._http = cliente or httpx.Client(
            timeout=settings.imagenes_timeout_segundos,
            headers={"User-Agent": settings.imagenes_user_agent},
            follow_redirects=False,
        )

    def descargar(self, url: str, dominios: list[str]) -> ImagenProcesada:
        contenido = self._descargar_bytes(url, dominios)
        tipo = filetype.guess(contenido)
        if tipo is None or tipo.mime not in MIMES_RASTER:
            raise ImagenesNoDisponiblesError("El archivo descargado no es una imagen permitida.")
        try:
            return self._procesador.recodificar(
                contenido, self._settings.imagenes_lado_maximo, self._settings.imagenes_ancho_minimo
            )
        except ArchivoInvalidoError as exc:
            raise ImagenesNoDisponiblesError("La imagen descargada no es válida.") from exc

    def cerrar(self) -> None:
        self._http.close()

    def _descargar_bytes(self, url: str, dominios: list[str]) -> bytes:
        actual = url
        for _ in range(self._settings.imagenes_max_redirecciones + 1):
            self._validar_destino(actual, dominios)
            siguiente, contenido = self._solicitar(actual)
            if contenido is not None:
                return contenido
            actual = urljoin(actual, siguiente)
        raise ImagenesNoDisponiblesError("Demasiadas redirecciones.")

    def _validar_destino(self, url: str, dominios: list[str]) -> None:
        partes = urlsplit(url)
        host = (partes.hostname or "").lower()
        if partes.scheme != ESQUEMA_PERMITIDO or not _dominio_permitido(host, dominios):
            raise ImagenesNoDisponiblesError("Destino de descarga no permitido.")
        try:
            ips = self._resolver(host)
        except OSError as exc:
            raise ImagenesNoDisponiblesError("No se pudo resolver el destino.") from exc
        if not ips or not all(_es_ip_publica(ip) for ip in ips):
            raise ImagenesNoDisponiblesError("El destino resuelve a una dirección no pública.")

    def _solicitar(self, url: str) -> tuple[str, bytes | None]:
        try:
            with self._http.stream("GET", url) as respuesta:
                if respuesta.status_code in CODIGOS_REDIRECCION:
                    return respuesta.headers.get("location", ""), None
                respuesta.raise_for_status()
                return "", self._leer_con_tope(respuesta)
        except httpx.HTTPError as exc:
            logger.warning("descarga_imagen_error tipo=%s", type(exc).__name__)
            raise ImagenesNoDisponiblesError() from exc

    def _leer_con_tope(self, respuesta: httpx.Response) -> bytes:
        datos = bytearray()
        for bloque in respuesta.iter_bytes(TAMANO_BLOQUE):
            datos.extend(bloque)
            if len(datos) > self._settings.imagenes_max_bytes:
                raise ImagenesNoDisponiblesError("La imagen supera el tamaño permitido.")
        return bytes(datos)
