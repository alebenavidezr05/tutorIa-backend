import base64
import logging

import openai

from app.core.config import Settings
from app.exceptions.base import GeneracionImagenError
from app.imagenes.base import ImagenesIAClient, ImagenGenerada
from app.imagenes.constantes import CALIDAD_IMAGEN_IA

logger = logging.getLogger(__name__)

MIME_POR_FORMATO = {"webp": "image/webp", "jpeg": "image/jpeg", "png": "image/png"}


class OpenAIImagenesClient(ImagenesIAClient):
    """Generación de ilustraciones educativas como último recurso, siempre en calidad baja."""

    def __init__(self, settings: Settings, cliente: openai.OpenAI | None = None) -> None:
        clave = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        self._settings = settings
        # max_retries=0: un reintento automático podría cobrar dos imágenes.
        self._cliente = cliente or openai.OpenAI(
            api_key=clave, timeout=settings.trabajo_visual_timeout_segundos, max_retries=0
        )

    def generar(self, descripcion: str, safety_identifier: str) -> ImagenGenerada:
        try:
            resultado = self._cliente.images.generate(
                model=self._settings.imagenes_ia_modelo,
                prompt=descripcion,
                quality=CALIDAD_IMAGEN_IA,
                size=self._settings.imagenes_ia_tamano,
                output_format=self._settings.imagenes_ia_formato,
                n=1,
                safety_identifier=safety_identifier,
            )
        except openai.OpenAIError as exc:
            logger.warning("imagen_ia_error tipo=%s", type(exc).__name__)
            raise GeneracionImagenError() from exc
        return self._traducir(resultado)

    def cerrar(self) -> None:
        self._cliente.close()

    def _traducir(self, resultado: object) -> ImagenGenerada:
        datos = resultado.data[0].b64_json  # type: ignore[attr-defined]
        if not datos:
            raise GeneracionImagenError()
        uso = getattr(resultado, "usage", None)
        return ImagenGenerada(
            contenido=base64.b64decode(datos),
            mime=MIME_POR_FORMATO[self._settings.imagenes_ia_formato],
            tokens_entrada=getattr(uso, "input_tokens", None),
            tokens_salida=getattr(uso, "output_tokens", None),
            modelo=self._settings.imagenes_ia_modelo,
        )
