"""Utilidades compartidas por los scripts de línea de comandos (Windows, Linux y macOS)."""

import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager

from app.core.config import Settings, get_settings
from app.core.contenedor import Contenedor, crear_contenedor
from app.core.database import crear_tablas
from app.core.fabrica import FabricaServicios
from app.core.logging import configurar_logging
from app.crypto.factory import registrar_cifrador


def preparar_consola() -> None:
    # La consola de Windows puede no ser UTF-8: se reemplazan caracteres en vez de fallar.
    for flujo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is not None:
            reconfigurar(encoding="utf-8", errors="replace")


@contextmanager
def contenedor_de_script(
    settings: Settings | None = None, crear: bool = True
) -> Iterator[Contenedor]:
    preparar_consola()
    configuracion = settings or get_settings()
    configurar_logging(configuracion.es_produccion)
    registrar_cifrador(configuracion)
    with ExitStack() as pila:
        contenedor = crear_contenedor(configuracion)
        pila.callback(contenedor.cerrar)
        if crear:
            crear_tablas(contenedor.engine)
        yield contenedor


@contextmanager
def servicios_de_script(settings: Settings | None = None) -> Iterator[FabricaServicios]:
    with contenedor_de_script(settings) as contenedor, contenedor.fabrica_sesiones() as session:
        yield FabricaServicios(contenedor, session)
