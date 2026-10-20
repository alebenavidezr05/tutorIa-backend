import logging
from typing import Any

import httpx

from app.exceptions.base import ImagenesNoDisponiblesError

logger = logging.getLogger(__name__)


def obtener_json(
    cliente: httpx.Client, url: str, parametros: dict[str, Any], proveedor: str
) -> Any:
    """Frontera de red de los proveedores de imágenes: todo error se traduce a uno propio."""
    try:
        respuesta = cliente.get(url, params=parametros)
        respuesta.raise_for_status()
        return respuesta.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("imagenes_error proveedor=%s tipo=%s", proveedor, type(exc).__name__)
        raise ImagenesNoDisponiblesError() from exc
