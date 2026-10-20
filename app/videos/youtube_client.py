"""YouTube Data API v3: solo metadatos documentados (sin descargas, transcripciones ni scraping)."""

import logging
import re
from typing import Any

import httpx

from app.core.config import Settings
from app.exceptions.base import VideosNoDisponiblesError
from app.videos.base import MetadatosVideo, VideosClient

logger = logging.getLogger(__name__)

URL_API = "https://www.googleapis.com/youtube/v3"
_PATRON_DURACION = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
SEGUNDOS_POR_HORA = 3600
SEGUNDOS_POR_MINUTO = 60
PARAMETROS_BUSQUEDA = {
    "part": "snippet",
    "type": "video",
    "videoDuration": "medium",
    "videoEmbeddable": "true",
    "safeSearch": "strict",
    "relevanceLanguage": "es",
    "regionCode": "CO",
}


def duracion_iso_a_segundos(duracion: str) -> int:
    coincidencia = _PATRON_DURACION.fullmatch(duracion or "")
    if not coincidencia:
        return 0
    horas, minutos, segundos = (int(g or 0) for g in coincidencia.groups())
    return horas * SEGUNDOS_POR_HORA + minutos * SEGUNDOS_POR_MINUTO + segundos


def _metadatos(item: dict[str, Any]) -> MetadatosVideo:
    snippet = item.get("snippet", {})
    estado = item.get("status", {})
    return MetadatosVideo(
        youtube_id=item["id"],
        titulo=snippet.get("title", ""),
        canal=snippet.get("channelTitle", ""),
        id_canal=snippet.get("channelId", ""),
        duracion_segundos=duracion_iso_a_segundos(
            item.get("contentDetails", {}).get("duration", "")
        ),
        idioma=(snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "")[:5],
        embeddable=bool(estado.get("embeddable")),
        es_para_ninos=bool(estado.get("madeForKids")),
    )


class YouTubeClient(VideosClient):
    def __init__(self, settings: Settings, cliente: httpx.Client | None = None) -> None:
        self._clave = (
            settings.youtube_api_key.get_secret_value() if settings.youtube_api_key else ""
        )
        self._http = cliente or httpx.Client(timeout=settings.imagenes_timeout_segundos)

    def obtener_metadatos(self, youtube_ids: list[str]) -> list[MetadatosVideo]:
        parametros = {"part": "snippet,contentDetails,status", "id": ",".join(youtube_ids)}
        return [_metadatos(i) for i in self._obtener("videos", parametros).get("items", [])]

    def buscar(self, tema: str, limite: int) -> list[MetadatosVideo]:
        parametros = {**PARAMETROS_BUSQUEDA, "q": tema, "maxResults": limite}
        items = self._obtener("search", parametros).get("items", [])
        ids = [i["id"]["videoId"] for i in items if i.get("id", {}).get("videoId")]
        return self.obtener_metadatos(ids) if ids else []

    def cerrar(self) -> None:
        self._http.close()

    def _obtener(self, recurso: str, parametros: dict[str, Any]) -> dict[str, Any]:
        try:
            respuesta = self._http.get(
                f"{URL_API}/{recurso}", params={**parametros, "key": self._clave}
            )
            respuesta.raise_for_status()
            datos: dict[str, Any] = respuesta.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("youtube_error recurso=%s tipo=%s", recurso, type(exc).__name__)
            raise VideosNoDisponiblesError() from exc
        return datos
