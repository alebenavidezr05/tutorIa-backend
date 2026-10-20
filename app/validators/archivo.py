import re

import filetype

from app.exceptions.base import ArchivoInvalidoError, ArchivoMuyGrandeError

MIME_TEXTO = "text/plain"
CARACTER_REEMPLAZO = "�"
LONGITUD_MAX_NOMBRE = 120
_PATRON_NOMBRE_INSEGURO = re.compile(r"[^\w.\- ]")


def _detectar_tipo_real(contenido: bytes) -> str | None:
    tipo = filetype.guess(contenido)
    return tipo.mime if tipo else None


def _es_texto_utf8(contenido: bytes) -> bool:
    # `errors="replace"` evita capturar excepciones: un byte inválido deja el carácter U+FFFD.
    return b"\x00" not in contenido and CARACTER_REEMPLAZO not in contenido.decode(
        "utf-8", errors="replace"
    )


def _nombre_seguro(nombre: str) -> str:
    base = nombre.replace("\\", "/").rsplit("/", 1)[-1]
    limpio = _PATRON_NOMBRE_INSEGURO.sub("_", base).strip(" .")
    return limpio[:LONGITUD_MAX_NOMBRE] or "archivo"


def _mime_detectado(contenido: bytes) -> str:
    mime = _detectar_tipo_real(contenido)
    if mime is None and _es_texto_utf8(contenido):
        return MIME_TEXTO
    if mime is None:
        raise ArchivoInvalidoError()
    return mime


def validar_archivo(
    nombre: str, contenido: bytes, tipos_permitidos: list[str], max_bytes: int
) -> tuple[str, str]:
    """Devuelve (mime real, nombre seguro). El tipo sale de los bytes, nunca de la extensión."""
    if len(contenido) > max_bytes:
        raise ArchivoMuyGrandeError()
    if not contenido:
        raise ArchivoInvalidoError("El archivo está vacío.")
    mime = _mime_detectado(contenido)
    if mime not in tipos_permitidos:
        raise ArchivoInvalidoError()
    return mime, _nombre_seguro(nombre)


def validar_texto_archivo(contenido: bytes, max_caracteres: int) -> str:
    if not _es_texto_utf8(contenido):
        raise ArchivoInvalidoError("El archivo de texto debe estar en UTF-8.")
    texto = contenido.decode("utf-8")
    if len(texto) > max_caracteres:
        raise ArchivoInvalidoError(f"El texto supera los {max_caracteres} caracteres permitidos.")
    return texto
