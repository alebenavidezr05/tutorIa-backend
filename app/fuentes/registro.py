from collections.abc import Callable

import httpx

from app.core.config import ConfigProveedor, Settings
from app.fuentes.adaptadores.ckan import CkanFuentesClient
from app.fuentes.adaptadores.http import crear_cliente_http
from app.fuentes.adaptadores.mediawiki import MediaWikiFuentesClient
from app.fuentes.adaptadores.rest_json import OpenAlexFuentesClient
from app.fuentes.base import FuentesClient
from app.fuentes.fake_client import FakeFuentesClient
from app.models.enums import CategoriaFuente

ConstructorFuentes = Callable[[ConfigProveedor, httpx.Client], FuentesClient]

# Agregar un proveedor = una clase de adaptador + una línea aquí + su entrada en FUENTES_PROVEEDORES.
ADAPTADORES: dict[str, ConstructorFuentes] = {
    "mediawiki": MediaWikiFuentesClient,
    "openalex": OpenAlexFuentesClient,
    "ckan": CkanFuentesClient,
}
ADAPTADOR_FALSO = "fake"


def _construir(config: ConfigProveedor, settings: Settings) -> FuentesClient:
    if config.adaptador == ADAPTADOR_FALSO:
        return FakeFuentesClient(config.id, CategoriaFuente(config.categoria), config.autoridad)
    if config.adaptador not in ADAPTADORES:
        raise ValueError(f"Adaptador de fuentes no implementado: {config.adaptador}")
    cliente = crear_cliente_http(settings.fuentes_user_agent, settings.fuentes_timeout_segundos)
    return ADAPTADORES[config.adaptador](config, cliente)


def construir_fuentes(settings: Settings) -> list[FuentesClient]:
    activos = [c for c in settings.fuentes_proveedores if c.activo]
    if not settings.fuentes_web_search_activa:
        activos = [c for c in activos if c.categoria != CategoriaFuente.WEB_GENERAL]
    return [_construir(c, settings) for c in activos]
