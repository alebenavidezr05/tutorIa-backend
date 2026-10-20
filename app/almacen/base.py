import logging
from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.exceptions.base import AlmacenamientoError

logger = logging.getLogger(__name__)


class Almacen(ABC):
    """Almacén privado de objetos (archivos del estudiante y copias de imágenes)."""

    @abstractmethod
    def guardar(self, clave: str, contenido: bytes, mime: str) -> None: ...

    @abstractmethod
    def leer(self, clave: str) -> bytes: ...

    @abstractmethod
    def eliminar(self, clave: str) -> None: ...

    def eliminar_sin_fallar(self, claves: Iterable[str]) -> set[str]:
        """Borrado de mejor esfuerzo tras un commit. Devuelve las claves que fallaron: las filas
        quedan marcadas ELIMINADO y la limpieza programada (`limpiar_datos_vencidos`) reintenta."""
        fallidas: set[str] = set()
        for clave in claves:
            try:
                self.eliminar(clave)
            except AlmacenamientoError:
                fallidas.add(clave)
        if fallidas:
            logger.warning("almacen_borrado_pendiente cantidad=%s", len(fallidas))
        return fallidas

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""
