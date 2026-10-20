import re

from app.exceptions.base import DatoInvalidoError

_PATRON_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_VIDEO = "https://www.youtube.com/watch?v={youtube_id}"


def validar_youtube_id(youtube_id: str) -> str:
    if not _PATRON_YOUTUBE_ID.fullmatch(youtube_id):
        raise DatoInvalidoError("El identificador de YouTube no es válido.")
    return youtube_id


def construir_url_video(youtube_id: str) -> str:
    return URL_VIDEO.format(youtube_id=validar_youtube_id(youtube_id))
