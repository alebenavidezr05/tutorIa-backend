from abc import ABC, abstractmethod
from collections.abc import Callable

from fastapi import BackgroundTasks


class TareasSegundoPlano(ABC):
    @abstractmethod
    def programar(self, tarea: Callable[[], None]) -> None: ...


class TareasFastAPI(TareasSegundoPlano):
    """Se ejecutan después de enviar la respuesta; el texto del tutor nunca espera la imagen."""

    def __init__(self, background_tasks: BackgroundTasks) -> None:
        self._background_tasks = background_tasks

    def programar(self, tarea: Callable[[], None]) -> None:
        self._background_tasks.add_task(tarea)


class TareasInmediatas(TareasSegundoPlano):
    """Para scripts: ejecuta la tarea en el acto."""

    def programar(self, tarea: Callable[[], None]) -> None:
        tarea()
