import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.contenedor import Contenedor, crear_contenedor
from app.core.database import crear_tablas
from app.core.fabrica import FabricaServicios
from app.core.logging import configurar_logging
from app.core.middleware import CabecerasSeguridadMiddleware, OrigenMiddleware
from app.core.seguridad import PREFIJO_API
from app.crypto.factory import registrar_cifrador
from app.exceptions.handlers import registrar_handlers
from app.routers import router_privado, router_publico, router_sesion

logger = logging.getLogger(__name__)

METODOS_CORS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
CABECERAS_CORS = ["Content-Type", "Accept"]


def _verificar_textos_legales(contenedor: Contenedor) -> None:
    """En producción no se arranca con marcadores {{...}} sin reemplazar en la política."""
    with contenedor.fabrica_sesiones() as session:
        pendientes = FabricaServicios(contenedor, session).politica.marcadores_pendientes()
    if contenedor.settings.es_produccion and pendientes:
        raise RuntimeError(
            f"La política de tratamiento tiene marcadores sin reemplazar: {pendientes}"
        )


def _recuperar_huerfanos(contenedor: Contenedor) -> None:
    with contenedor.fabrica_sesiones() as session:
        recuperados = FabricaServicios(contenedor, session).trabajo_visual.recuperar_huerfanos()
    if recuperados:
        logger.info("trabajos_visuales_huerfanos_recuperados cantidad=%s", recuperados)


def iniciar(settings: Settings) -> Contenedor:
    """Orden estricto del arranque (§18). También lo usan los scripts."""
    configurar_logging(settings.es_produccion)
    registrar_cifrador(settings)
    contenedor = crear_contenedor(settings)
    crear_tablas(contenedor.engine)
    _verificar_textos_legales(contenedor)
    _recuperar_huerfanos(contenedor)
    return contenedor


def create_app(settings: Settings | None = None) -> FastAPI:
    configuracion = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.contenedor = iniciar(configuracion)
        yield
        app.state.contenedor.cerrar()

    documentacion = not configuracion.es_produccion
    app = FastAPI(
        title="TutorIA API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if documentacion else None,
        redoc_url="/redoc" if documentacion else None,
        openapi_url="/openapi.json" if documentacion else None,
    )
    app.add_middleware(OrigenMiddleware, origenes_permitidos=configuracion.cors_origins)
    app.add_middleware(CabecerasSeguridadMiddleware, es_produccion=configuracion.es_produccion)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configuracion.cors_origins,
        allow_credentials=True,
        allow_methods=METODOS_CORS,
        allow_headers=CABECERAS_CORS,
    )
    registrar_handlers(app)
    app.include_router(router_publico, prefix=PREFIJO_API)
    app.include_router(router_sesion, prefix=PREFIJO_API)
    app.include_router(router_privado, prefix=PREFIJO_API)
    return app


app = create_app()
