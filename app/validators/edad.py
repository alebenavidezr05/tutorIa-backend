from datetime import date

from app.exceptions.base import DatoInvalidoError, EdadNoPermitidaError
from app.models.enums import GrupoEdad

EDAD_FIN_ADOLESCENCIA_TEMPRANA = 14


def calcular_edad(fecha_nacimiento: date, hoy: date) -> int:
    cumplio_este_ano = (hoy.month, hoy.day) >= (fecha_nacimiento.month, fecha_nacimiento.day)
    return hoy.year - fecha_nacimiento.year - (0 if cumplio_este_ano else 1)


def es_menor(fecha_nacimiento: date, hoy: date, edad_mayoria: int) -> bool:
    return calcular_edad(fecha_nacimiento, hoy) < edad_mayoria


def validar_fecha_nacimiento(fecha_nacimiento: date, hoy: date, edad_maxima: int) -> date:
    if fecha_nacimiento > hoy:
        raise DatoInvalidoError("La fecha de nacimiento no puede estar en el futuro.")
    if calcular_edad(fecha_nacimiento, hoy) > edad_maxima:
        raise DatoInvalidoError("Revisa la fecha de nacimiento.")
    return fecha_nacimiento


def validar_edad_minima(fecha_nacimiento: date, hoy: date, edad_minima: int) -> None:
    if calcular_edad(fecha_nacimiento, hoy) < edad_minima:
        raise EdadNoPermitidaError(f"TutorIA está disponible a partir de los {edad_minima} años.")


def grupo_edad(fecha_nacimiento: date, hoy: date, edad_mayoria: int) -> GrupoEdad:
    edad = calcular_edad(fecha_nacimiento, hoy)
    if edad >= edad_mayoria:
        return GrupoEdad.ADULTO
    if edad <= EDAD_FIN_ADOLESCENCIA_TEMPRANA:
        return GrupoEdad.ADOLESCENTE_TEMPRANO
    return GrupoEdad.ADOLESCENTE
