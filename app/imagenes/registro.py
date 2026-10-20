from collections.abc import Callable

import httpx

from app.core.config import ConfigProveedor, Settings
from app.imagenes.adaptadores.commons import CommonsImagenesClient
from app.imagenes.adaptadores.iiif_museo import IiifMuseoImagenesClient
from app.imagenes.base import ImagenesClient
from app.imagenes.fake_client import FakeImagenesClient
from app.models.enums import CategoriaImagen

ConstructorImagenes = Callable[[ConfigProveedor, httpx.Client], ImagenesClient]

# Agregar una colección = una clase de adaptador + una línea aquí + su entrada en IMAGENES_PROVEEDORES.
ADAPTADORES: dict[str, ConstructorImagenes] = {
    "mediawiki_commons": CommonsImagenesClient,
    "iiif_museo": IiifMuseoImagenesClient,
}
ADAPTADOR_FALSO = "fake"


def _construir(config: ConfigProveedor, settings: Settings) -> ImagenesClient:
    if config.adaptador == ADAPTADOR_FALSO:
        return FakeImagenesClient(config.id, CategoriaImagen(config.categoria), config.dominios)
    if config.adaptador not in ADAPTADORES:
        raise ValueError(f"Adaptador de imágenes no implementado: {config.adaptador}")
    cliente = httpx.Client(
        timeout=settings.imagenes_timeout_segundos,
        headers={"User-Agent": settings.imagenes_user_agent},
    )
    return ADAPTADORES[config.adaptador](config, cliente)


def construir_imagenes(settings: Settings) -> list[ImagenesClient]:
    return [_construir(c, settings) for c in settings.imagenes_proveedores if c.activo]
