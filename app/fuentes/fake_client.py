from datetime import date

from app.exceptions.base import FuentesNoDisponiblesError
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.models.enums import CategoriaFuente

FECHA_FALSA = date(2024, 1, 15)


class FakeFuentesClient(FuentesClient):
    """Una fuente fija por categoría, sin red. Permite simular caídas o resultados vacíos."""

    def __init__(
        self, proveedor: str, categoria: CategoriaFuente, autoridad: int | None = None
    ) -> None:
        super().__init__(proveedor, categoria, autoridad)
        self.falla = False
        self.vacio = False

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        if self.falla:
            raise FuentesNoDisponiblesError()
        if self.vacio:
            return []
        slug = "-".join(consulta.lower().split())[:60] or "tema"
        return [
            FuenteCandidata(
                titulo=f"{consulta.capitalize()} ({self.categoria.value.lower()})",
                autor=f"Autor de {self.proveedor}",
                sitio=f"Sitio {self.proveedor}",
                url=f"https://fuentes.example.org/{self.proveedor}/{slug}",
                extracto=f"Extracto verificable sobre {consulta}.",
                categoria=self.categoria,
                autoridad=self.autoridad_base(),
                proveedor=self.proveedor,
                idioma=idioma,
                doi=f"10.0000/{self.proveedor}.{slug}"
                if self.categoria == CategoriaFuente.ACADEMICA_ABIERTA
                else None,
                fecha_publicacion=FECHA_FALSA,
                licencia="CC BY 4.0",
                revisada_por_pares=self.categoria == CategoriaFuente.ACADEMICA_ABIERTA,
            )
        ][:limite]
