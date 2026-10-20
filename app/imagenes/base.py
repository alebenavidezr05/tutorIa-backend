from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.exceptions.base import ImagenesNoDisponiblesError
from app.models.enums import CategoriaImagen


@dataclass(frozen=True)
class ImagenCandidata:
    titulo: str
    descripcion: str
    autor: str | None
    url_origen: str
    url_archivo: str
    mime: str
    ancho: int
    alto: int
    licencia: str
    url_licencia: str | None
    categoria: CategoriaImagen
    proveedor: str


class ImagenesClient(ABC):
    """Búsqueda en colecciones de imágenes con licencia abierta."""

    def __init__(self, proveedor: str, categoria: CategoriaImagen, dominios: list[str]) -> None:
        self.proveedor = proveedor
        self.categoria = categoria
        self.dominios = dominios

    @abstractmethod
    def buscar(self, consulta: str, limite: int) -> list[ImagenCandidata]: ...

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""


@dataclass(frozen=True)
class ImagenProcesada:
    contenido: bytes
    mime: str
    ancho: int
    alto: int


@dataclass(frozen=True)
class ImagenGenerada:
    contenido: bytes
    mime: str
    tokens_entrada: int | None
    tokens_salida: int | None
    modelo: str


class DescargadorImagenes(ABC):
    @abstractmethod
    def descargar(self, url: str, dominios: list[str]) -> ImagenProcesada: ...

    def intentar_descargar(self, url: str, dominios: list[str]) -> ImagenProcesada | None:
        """Una candidata que no se puede copiar de forma segura se descarta y se prueba la siguiente."""
        try:
            return self.descargar(url, dominios)
        except ImagenesNoDisponiblesError:
            return None

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""


class ProcesadorImagenes(ABC):
    @abstractmethod
    def recodificar(
        self, contenido: bytes, lado_maximo: int, ancho_minimo: int = 0
    ) -> ImagenProcesada:
        """Abre, valida y re-codifica la imagen eliminando metadatos (EXIF/GPS)."""


class ImagenesIAClient(ABC):
    @abstractmethod
    def generar(self, descripcion: str, safety_identifier: str) -> ImagenGenerada: ...

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""
