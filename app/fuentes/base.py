from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date

from app.models.enums import CategoriaFuente

# Escala 2–4: no existen fuentes de autoridad 1, porque las editables por cualquiera se excluyen
# por diseño (fuentes/bloqueo.py). Ninguna fuente por debajo del piso llega al modelo.
AUTORIDAD_PISO = 2
AUTORIDAD_POR_CATEGORIA = {
    CategoriaFuente.ACADEMICA_ABIERTA: 3,
    CategoriaFuente.INSTITUCIONAL_OFICIAL: 4,
    CategoriaFuente.EDUCATIVA_ABIERTA: 3,
    CategoriaFuente.REFERENCIA: 3,
    CategoriaFuente.PRENSA_CONFIABLE: 2,
    CategoriaFuente.CURADA: 3,
    CategoriaFuente.WEB_GENERAL: 2,
}
# Una búsqueda web abierta nunca supera esta autoridad, aunque la configuración diga otra cosa.
AUTORIDAD_MAXIMA_WEB = 2


@dataclass(frozen=True)
class FuenteCandidata:
    titulo: str
    autor: str | None
    sitio: str
    url: str
    extracto: str
    categoria: CategoriaFuente
    autoridad: int
    proveedor: str
    idioma: str
    doi: str | None = None
    fecha_publicacion: date | None = None
    licencia: str | None = None
    revisada_por_pares: bool | None = None


class FuentesClient(ABC):
    def __init__(self, proveedor: str, categoria: CategoriaFuente, autoridad: int | None) -> None:
        self.proveedor = proveedor
        self.categoria = categoria
        self._autoridad = autoridad

    @abstractmethod
    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]: ...

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""

    def autoridad_base(self) -> int:
        autoridad = self._autoridad or AUTORIDAD_POR_CATEGORIA[self.categoria]
        if self.categoria == CategoriaFuente.WEB_GENERAL:
            return min(autoridad, AUTORIDAD_MAXIMA_WEB)
        return autoridad
