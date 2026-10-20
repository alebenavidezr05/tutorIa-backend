from app.correo.base import Correo, CorreoClient
from app.exceptions.base import CorreoNoEnviadoError


class FakeCorreoClient(CorreoClient):
    """Guarda los correos en memoria (desarrollo y pruebas); nunca los envía ni los registra."""

    def __init__(self) -> None:
        self.enviados: list[Correo] = []
        self.falla = False

    def enviar(self, correo: Correo) -> None:
        if self.falla:
            raise CorreoNoEnviadoError()
        self.enviados.append(correo)
