from app.crypto.base import Cifrador
from app.exceptions.base import CifradoError


class _RegistroCifrador:
    """Los TypeDecorator no reciben dependencias: leen el cifrador de este registro de proceso."""

    def __init__(self) -> None:
        self._cifrador: Cifrador | None = None

    def registrar(self, cifrador: Cifrador) -> None:
        self._cifrador = cifrador

    def obtener(self) -> Cifrador:
        if self._cifrador is None:
            raise CifradoError("El cifrador no está registrado; se debe inicializar al arrancar.")
        return self._cifrador


registro_cifrador = _RegistroCifrador()
