from app.exceptions.base import MensajeNoPermitidoError
from app.models.enums import IntencionMensaje
from app.validators.inyeccion import PATRONES_INYECCION
from app.validators.tema import PATRONES_RESOLVER_TAREA
from app.validators.texto import (
    compilar,
    contiene_alguno,
    normalizar_para_comparar,
    normalizar_texto,
)

LONGITUD_MIN_MENSAJE = 1
LONGITUD_MAX_MENSAJE = 1500
PATRONES_PIDE_RESOLUCION = (
    *PATRONES_RESOLVER_TAREA,
    *compilar(
        r"\bcual es (la )?respuesta\b",
        r"\bdime (la )?respuesta\b",
        r"\bsolo (dame|dime) el resultado\b",
        r"\bresuelvem[eo]\b",
        r"\bhazlo tu\b",
        r"\bhazme (el|la|los|las)\b",
    ),
)


def _validar_longitud_mensaje(texto: str) -> None:
    if not LONGITUD_MIN_MENSAJE <= len(texto) <= LONGITUD_MAX_MENSAJE:
        raise MensajeNoPermitidoError(
            f"El mensaje debe tener entre {LONGITUD_MIN_MENSAJE} y {LONGITUD_MAX_MENSAJE} caracteres."
        )


def _validar_inyeccion(texto: str) -> None:
    if contiene_alguno(normalizar_para_comparar(texto), PATRONES_INYECCION):
        raise MensajeNoPermitidoError()


def validar_mensaje_chat(texto: str) -> str:
    limpio = normalizar_texto(texto)
    _validar_longitud_mensaje(limpio)
    _validar_inyeccion(limpio)
    return limpio


def clasificar_intencion(texto: str) -> IntencionMensaje:
    """Pedir que le resuelvan algo no se rechaza en el chat: activa el modo guía."""
    if contiene_alguno(normalizar_para_comparar(texto), PATRONES_PIDE_RESOLUCION):
        return IntencionMensaje.RESOLVER_TAREA
    return IntencionMensaje.CONSULTA
