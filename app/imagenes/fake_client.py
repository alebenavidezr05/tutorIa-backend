import io
from dataclasses import dataclass, field

from PIL import Image

from app.exceptions.base import GeneracionImagenError, ImagenesNoDisponiblesError
from app.imagenes.base import (
    DescargadorImagenes,
    ImagenCandidata,
    ImagenesClient,
    ImagenesIAClient,
    ImagenGenerada,
    ImagenProcesada,
)
from app.models.enums import CategoriaImagen

ANCHO_FALSO = 800
ALTO_FALSO = 600
COLOR_FALSO = (40, 120, 200)
MODELO_IMAGEN_FALSO = "fake-image"


def imagen_falsa(ancho: int = ANCHO_FALSO, alto: int = ALTO_FALSO, formato: str = "WEBP") -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (ancho, alto), COLOR_FALSO).save(salida, formato)
    return salida.getvalue()


class FakeImagenesClient(ImagenesClient):
    def __init__(self, proveedor: str, categoria: CategoriaImagen, dominios: list[str]) -> None:
        super().__init__(proveedor, categoria, dominios)
        self.licencia = "CC BY-SA 4.0"
        self.falla = False
        self.vacio = False

    def buscar(self, consulta: str, limite: int) -> list[ImagenCandidata]:
        if self.falla:
            raise ImagenesNoDisponiblesError()
        if self.vacio:
            return []
        dominio = self.dominios[0] if self.dominios else "imagenes.example.org"
        slug = "-".join(consulta.lower().split())
        return [
            ImagenCandidata(
                titulo=consulta,
                descripcion=f"Imagen educativa de {consulta}",
                autor="Autora de ejemplo",
                url_origen=f"https://{dominio}/pagina/{slug}",
                url_archivo=f"https://{dominio}/archivo/{slug}.jpg",
                mime="image/jpeg",
                ancho=ANCHO_FALSO,
                alto=ALTO_FALSO,
                licencia=self.licencia,
                url_licencia="https://creativecommons.org/licenses/by-sa/4.0/",
                categoria=self.categoria,
                proveedor=self.proveedor,
            )
        ][:limite]


@dataclass
class FakeDescargador(DescargadorImagenes):
    falla: bool = False
    urls: list[str] = field(default_factory=list)

    def descargar(self, url: str, dominios: list[str]) -> ImagenProcesada:
        self.urls.append(url)
        if self.falla:
            raise ImagenesNoDisponiblesError()
        return ImagenProcesada(imagen_falsa(), "image/webp", ANCHO_FALSO, ALTO_FALSO)


@dataclass
class FakeImagenesIAClient(ImagenesIAClient):
    falla: bool = False
    llamadas: list[tuple[str, str]] = field(default_factory=list)

    def generar(self, descripcion: str, safety_identifier: str) -> ImagenGenerada:
        self.llamadas.append((descripcion, safety_identifier))
        if self.falla:
            raise GeneracionImagenError()
        return ImagenGenerada(imagen_falsa(), "image/webp", 50, 1000, MODELO_IMAGEN_FALSO)
