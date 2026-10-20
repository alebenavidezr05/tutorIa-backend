import base64
import logging
from typing import Any

import openai

from app.core.config import Settings
from app.exceptions.base import ModeracionNoDisponibleError
from app.moderacion.base import ModeradorClient, ResultadoModeracion

logger = logging.getLogger(__name__)


def _url_datos(contenido: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(contenido).decode()}"


class OpenAIModeracionClient(ModeradorClient):
    """Endpoint de moderación de OpenAI (gratuito). Único lugar que captura errores de ese SDK."""

    def __init__(self, settings: Settings, cliente: openai.OpenAI | None = None) -> None:
        clave = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
        self._modelo = settings.moderacion_modelo
        self._cliente = cliente or openai.OpenAI(
            api_key=clave, timeout=settings.llm_timeout_segundos
        )

    def moderar_texto(self, texto: str) -> ResultadoModeracion:
        return self._moderar(texto)

    def moderar_imagen(self, contenido: bytes, mime: str) -> ResultadoModeracion:
        # Solo algunas categorías aplican a imágenes; las demás llegan en 0 según la documentación.
        entrada = [{"type": "image_url", "image_url": {"url": _url_datos(contenido, mime)}}]
        return self._moderar(entrada)

    def cerrar(self) -> None:
        self._cliente.close()

    def _moderar(self, entrada: Any) -> ResultadoModeracion:
        try:
            respuesta = self._cliente.moderations.create(model=self._modelo, input=entrada)
        except openai.OpenAIError as exc:
            logger.warning("moderacion_error tipo=%s", type(exc).__name__)
            raise ModeracionNoDisponibleError() from exc
        resultado = respuesta.results[0]
        puntajes = resultado.category_scores.model_dump(by_alias=True)
        return ResultadoModeracion(
            marcado=bool(resultado.flagged),
            categorias={k: float(v) for k, v in puntajes.items() if v is not None},
        )
