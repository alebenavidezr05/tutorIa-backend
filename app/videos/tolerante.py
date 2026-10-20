import logging

from app.exceptions.base import VideosNoDisponiblesError
from app.videos.base import MetadatosVideo, VideosClient

logger = logging.getLogger(__name__)


class VideosTolerante(VideosClient):
    """Si YouTube no responde, el tutor sigue sin video: se devuelve una lista vacía."""

    def __init__(self, interno: VideosClient) -> None:
        self.interno = interno

    def obtener_metadatos(self, youtube_ids: list[str]) -> list[MetadatosVideo]:
        try:
            return self.interno.obtener_metadatos(youtube_ids)
        except VideosNoDisponiblesError:
            logger.warning("videos_no_disponibles operacion=metadatos")
            return []

    def buscar(self, tema: str, limite: int) -> list[MetadatosVideo]:
        try:
            return self.interno.buscar(tema, limite)
        except VideosNoDisponiblesError:
            logger.warning("videos_no_disponibles operacion=buscar")
            return []

    def cerrar(self) -> None:
        self.interno.cerrar()
