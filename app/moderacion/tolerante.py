import logging

from app.exceptions.base import ModeracionNoDisponibleError
from app.moderacion.base import ModeradorClient, ResultadoModeracion

logger = logging.getLogger(__name__)

NO_DISPONIBLE = ResultadoModeracion(marcado=False, disponible=False)


class ModeradorTolerante(ModeradorClient):
    """La moderación es fail-open (§11.3): si el proveedor cae, se informa y el flujo sigue con la
    segunda capa (el `ambito` del modelo). Traducir el fallo aquí mantiene los services sin try."""

    def __init__(self, interno: ModeradorClient) -> None:
        self.interno = interno

    def moderar_texto(self, texto: str) -> ResultadoModeracion:
        try:
            return self.interno.moderar_texto(texto)
        except ModeracionNoDisponibleError:
            logger.warning("moderacion_no_disponible entrada=texto")
            return NO_DISPONIBLE

    def moderar_imagen(self, contenido: bytes, mime: str) -> ResultadoModeracion:
        try:
            return self.interno.moderar_imagen(contenido, mime)
        except ModeracionNoDisponibleError:
            logger.warning("moderacion_no_disponible entrada=imagen")
            return NO_DISPONIBLE

    def cerrar(self) -> None:
        self.interno.cerrar()
