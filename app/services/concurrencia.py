import logging
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ResultadoParalelo(Generic[T]):
    resultados: list[T] = field(default_factory=list)
    errores: list[BaseException] = field(default_factory=list)
    lentos: int = 0

    @property
    def degradado(self) -> bool:
        return bool(self.errores) or self.lentos > 0


def ejecutar_en_paralelo(
    tareas: Sequence[Callable[[], list[T]]], timeout_segundos: float
) -> ResultadoParalelo[T]:
    """Como `consultar_en_paralelo`, pero informa qué falló para decidir cómo degradar."""
    if not tareas:
        return ResultadoParalelo()
    ejecutor = ThreadPoolExecutor(max_workers=len(tareas))
    futuros: list[Future[list[T]]] = [ejecutor.submit(t) for t in tareas]
    terminados, pendientes = wait(futuros, timeout=timeout_segundos)
    ejecutor.shutdown(wait=False, cancel_futures=True)
    errores = [e for f in terminados if (e := f.exception()) is not None]
    if errores or pendientes:
        logger.warning(
            "proveedores_sin_respuesta fallidos=%s lentos=%s", len(errores), len(pendientes)
        )
    resultados = [r for f in terminados if f.exception() is None for r in f.result()]
    return ResultadoParalelo(resultados, errores, len(pendientes))


def consultar_en_paralelo(
    tareas: Sequence[Callable[[], list[T]]], timeout_segundos: float
) -> list[T]:
    """Un proveedor caído o lento no rompe la búsqueda: se usan solo los que respondan a tiempo."""
    return ejecutar_en_paralelo(tareas, timeout_segundos).resultados
