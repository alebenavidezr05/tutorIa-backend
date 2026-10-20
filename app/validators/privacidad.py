import re

MARCADOR_CORREO = "[correo omitido]"
MARCADOR_TELEFONO = "[teléfono omitido]"
MARCADOR_IDENTIFICACION = "[documento omitido]"
_PATRON_CORREO = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
# Celulares colombianos (3xx xxx xxxx, con o sin +57) y fijos con indicativo 60x.
_PATRON_TELEFONO = re.compile(r"(?<!\d)(\+?57[\s.-]?)?(3\d{2}|60\d)[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
# Solo números precedidos de una palabra de documento: un número suelto puede ser matemática.
_PATRON_IDENTIFICACION = re.compile(
    r"\b(c\.?\s?c\.?|t\.?\s?i\.?|c[eé]dula|documento|identificaci[oó]n|pasaporte|nuip)"
    r"[^\d\n]{0,25}\d[\d.\s-]{4,14}\d",
    re.IGNORECASE,
)


def _redactar_correos(texto: str) -> str:
    return _PATRON_CORREO.sub(MARCADOR_CORREO, texto)


def _redactar_telefonos(texto: str) -> str:
    return _PATRON_TELEFONO.sub(MARCADOR_TELEFONO, texto)


def _redactar_identificaciones(texto: str) -> str:
    return _PATRON_IDENTIFICACION.sub(MARCADOR_IDENTIFICACION, texto)


def redactar_datos_personales(texto: str) -> str:
    return _redactar_telefonos(_redactar_identificaciones(_redactar_correos(texto)))


def enmascarar_correo(correo: str) -> str:
    usuario, _, dominio = correo.partition("@")
    return f"{usuario[:1]}***@{dominio}"
