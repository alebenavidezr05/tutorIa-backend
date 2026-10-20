from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResultadoModeracion:
    marcado: bool
    categorias: dict[str, float] = field(default_factory=dict)
    disponible: bool = True


class ModeradorClient(ABC):
    @abstractmethod
    def moderar_texto(self, texto: str) -> ResultadoModeracion: ...

    @abstractmethod
    def moderar_imagen(self, contenido: bytes, mime: str) -> ResultadoModeracion: ...

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""
