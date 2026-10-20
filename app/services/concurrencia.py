import logging
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def consultar_en_paralelo(
    tareas: Sequence[Callable[[], list[T]]], timeout_segundos: float
) -> list[T]:
    """Un proveedor caído o lento no rompe la búsqueda: se usan solo los que respondan a tiempo."""
    if not tareas:
        return []
    ejecutor = ThreadPoolExecutor(max_workers=len(tareas))
    futuros: list[Future[list[T]]] = [ejecutor.submit(t) for t in tareas]
    terminados, pendientes = wait(futuros, timeout=timeout_segundos)
    ejecutor.shutdown(wait=False, cancel_futures=True)
    fallidos = [f for f in terminados if f.exception() is not None]
    if fallidos or pendientes:
        logger.warning(
            "proveedores_sin_respuesta fallidos=%s lentos=%s", len(fallidos), len(pendientes)
        )
    return [r for f in terminados if f.exception() is None for r in f.result()]
