import re

from app.exceptions.base import DatoInvalidoError
from app.models.enums import TipoNivel
from app.validators.texto import normalizar_texto

LONGITUD_MIN_CONTRASENA = 8
LONGITUD_MAX_CONTRASENA = 64
MAX_BYTES_BCRYPT = 72
LONGITUD_MIN_NOMBRE = 2
LONGITUD_MAX_NOMBRE = 100
GRADOS_COLEGIO = ("8", "9", "10", "11")
NIVELES_UNIVERSIDAD = ("Técnico", "Tecnólogo", "Pregrado", "Posgrado")
NIVELES_POR_TIPO = {
    TipoNivel.COLEGIO: GRADOS_COLEGIO,
    TipoNivel.UNIVERSIDAD_TECNICA: NIVELES_UNIVERSIDAD,
}
_PATRON_LETRA = re.compile(r"[^\W\d_]")
_PATRON_DIGITO = re.compile(r"\d")


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def _validar_longitud_contrasena(contrasena: str) -> None:
    if not LONGITUD_MIN_CONTRASENA <= len(contrasena) <= LONGITUD_MAX_CONTRASENA:
        raise DatoInvalidoError(
            f"La contraseña debe tener entre {LONGITUD_MIN_CONTRASENA} "
            f"y {LONGITUD_MAX_CONTRASENA} caracteres."
        )
    # bcrypt ignora lo que pase de 72 bytes: se rechaza para no aceptar contraseñas truncadas.
    if len(contrasena.encode()) > MAX_BYTES_BCRYPT:
        raise DatoInvalidoError("La contraseña es demasiado larga.")


def _validar_composicion_contrasena(contrasena: str) -> None:
    if not (_PATRON_LETRA.search(contrasena) and _PATRON_DIGITO.search(contrasena)):
        raise DatoInvalidoError("La contraseña debe tener al menos una letra y un número.")


def validar_contrasena(contrasena: str) -> str:
    _validar_longitud_contrasena(contrasena)
    _validar_composicion_contrasena(contrasena)
    return contrasena


def validar_nombre(nombre: str) -> str:
    limpio = normalizar_texto(nombre)
    if not LONGITUD_MIN_NOMBRE <= len(limpio) <= LONGITUD_MAX_NOMBRE:
        raise DatoInvalidoError(
            f"El nombre debe tener entre {LONGITUD_MIN_NOMBRE} y {LONGITUD_MAX_NOMBRE} caracteres."
        )
    return limpio


def validar_nivel_educativo(tipo_nivel: TipoNivel, nivel_educativo: str) -> str:
    permitidos = NIVELES_POR_TIPO[tipo_nivel]
    nivel = normalizar_texto(nivel_educativo)
    if nivel not in permitidos:
        raise DatoInvalidoError(
            f"El nivel educativo debe ser uno de: {', '.join(permitidos)}.",
            detalles=[{"campo": "nivel_educativo", "mensaje": "valor no permitido"}],
        )
    return nivel
