from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Correo:
    destinatario: str
    asunto: str
    texto: str


class CorreoClient(ABC):
    @abstractmethod
    def enviar(self, correo: Correo) -> None: ...

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""
