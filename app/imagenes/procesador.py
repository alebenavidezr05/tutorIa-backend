import io

from PIL import Image, ImageOps, UnidentifiedImageError

from app.exceptions.base import ArchivoInvalidoError
from app.imagenes.base import ImagenProcesada, ProcesadorImagenes

FORMATO_SALIDA = "WEBP"
MIME_SALIDA = "image/webp"
CALIDAD_WEBP = 85
MODOS_CON_TRANSPARENCIA = ("RGBA", "LA", "P")
# Protege contra "bombas de descompresión": imágenes con dimensiones absurdas.
PIXELES_MAXIMOS = 40_000_000
# Pillow puede fallar con EXIF malformado de varias formas; todas significan "imagen inválida".
ERRORES_DE_LECTURA = (
    UnidentifiedImageError,
    OSError,
    ValueError,
    AttributeError,
    Image.DecompressionBombError,
)


class ProcesadorPillow(ProcesadorImagenes):
    """Re-codifica a WebP: elimina EXIF/GPS y cualquier contenido ajeno a los píxeles."""

    def recodificar(
        self, contenido: bytes, lado_maximo: int, ancho_minimo: int = 0
    ) -> ImagenProcesada:
        imagen = self._abrir_orientada(contenido)
        if imagen.width < ancho_minimo:
            raise ArchivoInvalidoError("La imagen es demasiado pequeña.")
        imagen.thumbnail((lado_maximo, lado_maximo))
        modo = "RGBA" if imagen.mode in MODOS_CON_TRANSPARENCIA else "RGB"
        salida = io.BytesIO()
        imagen.convert(modo).save(salida, FORMATO_SALIDA, quality=CALIDAD_WEBP)
        return ImagenProcesada(salida.getvalue(), MIME_SALIDA, imagen.width, imagen.height)

    def _abrir_orientada(self, contenido: bytes) -> Image.Image:
        Image.MAX_IMAGE_PIXELS = PIXELES_MAXIMOS
        try:
            imagen = Image.open(io.BytesIO(contenido))
            imagen.load()
            return ImageOps.exif_transpose(imagen)
        except ERRORES_DE_LECTURA as exc:
            raise ArchivoInvalidoError("No pudimos leer la imagen.") from exc
