from app.exceptions.base import VideosNoDisponiblesError
from app.videos.base import MetadatosVideo, VideosClient

DURACION_FALSA = 600


class FakeVideosClient(VideosClient):
    def __init__(self) -> None:
        self.falla = False
        self.metadatos: dict[str, MetadatosVideo] = {}

    def obtener_metadatos(self, youtube_ids: list[str]) -> list[MetadatosVideo]:
        if self.falla:
            raise VideosNoDisponiblesError()
        return [self.metadatos.get(i) or _metadatos_falsos(i) for i in youtube_ids]

    def buscar(self, tema: str, limite: int) -> list[MetadatosVideo]:
        if self.falla:
            raise VideosNoDisponiblesError()
        return []


def _metadatos_falsos(youtube_id: str) -> MetadatosVideo:
    return MetadatosVideo(
        youtube_id=youtube_id,
        titulo=f"Video {youtube_id}",
        canal="Canal educativo",
        id_canal="UCcanalfalso",
        duracion_segundos=DURACION_FALSA,
        idioma="es",
        embeddable=True,
        es_para_ninos=False,
    )
