import logging
from collections.abc import Callable

import httpx

from app.core.config import ConfigProveedor, Settings
from app.fuentes.adaptadores.ckan import CkanFuentesClient
from app.fuentes.adaptadores.http import crear_cliente_http
from app.fuentes.adaptadores.medlineplus import MedlinePlusFuentesClient
from app.fuentes.adaptadores.rest_json import OpenAlexFuentesClient
from app.fuentes.base import FuentesClient
from app.fuentes.bloqueo import es_dominio_bloqueado
from app.fuentes.fake_client import FakeFuentesClient
from app.models.enums import CategoriaFuente

ConstructorFuentes = Callable[[ConfigProveedor, httpx.Client], FuentesClient]

# Agregar un proveedor = una clase de adaptador + una línea aquí + su entrada en FUENTES_PROVEEDORES.
ADAPTADORES: dict[str, ConstructorFuentes] = {
    "openalex": OpenAlexFuentesClient,
    "ckan": CkanFuentesClient,
    "medlineplus": MedlinePlusFuentesClient,
}
ADAPTADOR_FALSO = "fake"
ADAPTADOR_OPENALEX = "openalex"

logger = logging.getLogger(__name__)


def validar_proveedores_texto(settings: Settings) -> None:
    """Ningún proveedor de texto (activo o no) puede apuntar a un dominio editable por cualquiera.
    Se comprueba al arrancar, en todos los entornos. Las imágenes tienen su propio registro."""
    bloqueados = settings.fuentes_dominios_bloqueados
    invalidos = sorted(
        {
            c.id
            for c in settings.fuentes_proveedores
            for destino in (c.base_url, *c.dominios)
            if destino and es_dominio_bloqueado(destino, bloqueados)
        }
    )
    if invalidos:
        raise ValueError(
            "FUENTES_PROVEEDORES incluye dominios bloqueados (fuentes editables por cualquiera, "
            f"ver docs/fuentes.md): {', '.join(invalidos)}"
        )


def _construir(config: ConfigProveedor, settings: Settings) -> FuentesClient:
    if config.adaptador == ADAPTADOR_FALSO:
        return FakeFuentesClient(config.id, CategoriaFuente(config.categoria), config.autoridad)
    if config.adaptador not in ADAPTADORES:
        raise ValueError(f"Adaptador de fuentes no implementado: {config.adaptador}")
    cliente = crear_cliente_http(settings.fuentes_user_agent, settings.fuentes_timeout_segundos)
    if config.adaptador == ADAPTADOR_OPENALEX:
        return OpenAlexFuentesClient(config, cliente, settings.openalex_api_key)
    return ADAPTADORES[config.adaptador](config, cliente)


def avisar_configuracion(settings: Settings, activos: list[ConfigProveedor]) -> None:
    """Sin clave OpenAlex funciona igual, pero su presupuesto diario es muy limitado."""
    usa_openalex = any(c.adaptador == ADAPTADOR_OPENALEX for c in activos)
    clave = settings.openalex_api_key
    if settings.es_produccion and usa_openalex and not (clave and clave.get_secret_value()):
        logger.warning("OpenAlex sin API key: presupuesto diario muy limitado")


def construir_fuentes(settings: Settings) -> list[FuentesClient]:
    validar_proveedores_texto(settings)
    activos = [c for c in settings.fuentes_proveedores if c.activo]
    if not settings.fuentes_web_search_activa:
        activos = [c for c in activos if c.categoria != CategoriaFuente.WEB_GENERAL]
    avisar_configuracion(settings, activos)
    return [_construir(c, settings) for c in activos]
