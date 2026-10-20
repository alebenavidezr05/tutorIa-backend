from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class MetadatosVideo:
    youtube_id: str
    titulo: str
    canal: str
    id_canal: str
    duracion_segundos: int
    idioma: str
    embeddable: bool
    es_para_ninos: bool


class VideosClient(ABC):
    @abstractmethod
    def obtener_metadatos(self, youtube_ids: list[str]) -> list[MetadatosVideo]: ...

    @abstractmethod
    def buscar(self, tema: str, limite: int) -> list[MetadatosVideo]: ...

    def cerrar(self) -> None:
        """Libera conexiones; los adaptadores sin recursos no hacen nada."""
