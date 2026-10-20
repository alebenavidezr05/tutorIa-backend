from app.exceptions.base import TemaNoPermitidoError
from app.validators.inyeccion import PATRONES_INYECCION
from app.validators.texto import (
    compilar,
    contiene_alguno,
    normalizar_para_comparar,
    normalizar_texto,
)

LONGITUD_MIN_TEMA = 3
LONGITUD_MAX_TEMA = 200
PATRONES_RESOLVER_TAREA = compilar(
    r"\bresuelve\w*",
    r"\bresolver (el|la|los|las|este|esta|mi)\b",
    r"\bhaz(me)? (la|mi|el|mis) (tarea|taller|ejercicio|examen|trabajo)",
    r"\bdame (las|la) respuestas?\b",
    r"\b(las|la) respuestas? (del|de la|de mi) (examen|taller|tarea|quiz)",
    r"\bhazme el (ensayo|trabajo|informe)",
)


def _validar_longitud_tema(tema: str) -> None:
    if not LONGITUD_MIN_TEMA <= len(tema) <= LONGITUD_MAX_TEMA:
        raise TemaNoPermitidoError(
            f"El tema debe tener entre {LONGITUD_MIN_TEMA} y {LONGITUD_MAX_TEMA} caracteres."
        )


def _validar_patrones_tema(tema: str) -> None:
    normalizado = normalizar_para_comparar(tema)
    if contiene_alguno(normalizado, PATRONES_INYECCION):
        raise TemaNoPermitidoError()
    if contiene_alguno(normalizado, PATRONES_RESOLVER_TAREA):
        raise TemaNoPermitidoError(
            "TutorIA enseña, no resuelve tareas. Escribe el tema que quieres aprender."
        )


def validar_tema(tema: str) -> str:
    limpio = normalizar_texto(tema)
    _validar_longitud_tema(limpio)
    _validar_patrones_tema(limpio)
    return limpio
