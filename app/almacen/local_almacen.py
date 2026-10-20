import re
from pathlib import Path

from app.almacen.base import Almacen
from app.exceptions.base import AlmacenamientoError

_PATRON_CLAVE = re.compile(r"^[A-Za-z0-9/_.-]+$")


class LocalAlmacen(Almacen):
    """Solo desarrollo: guarda en disco. Producción usa S3 privado con SSE-KMS."""

    def __init__(self, ruta: str) -> None:
        self._raiz = Path(ruta).resolve()

    def guardar(self, clave: str, contenido: bytes, mime: str) -> None:
        destino = self._ruta(clave)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)

    def leer(self, clave: str) -> bytes:
        destino = self._ruta(clave)
        if not destino.is_file():
            raise AlmacenamientoError()
        return destino.read_bytes()

    def eliminar(self, clave: str) -> None:
        self._ruta(clave).unlink(missing_ok=True)

    def _ruta(self, clave: str) -> Path:
        destino = (self._raiz / clave).resolve()
        # Evita que una clave con ".." escape del directorio del almacén.
        if not _PATRON_CLAVE.fullmatch(clave) or self._raiz not in destino.parents:
            raise AlmacenamientoError()
        return destino
