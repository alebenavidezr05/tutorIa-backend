"""Referencias APA 7 en español construidas de forma determinista desde metadatos (sin LLM)."""

from datetime import date, datetime

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
SIN_FECHA = "s. f."
PREFIJO_DOI = "https://doi.org/"


def _fecha_larga(fecha: date) -> str:
    return f"{fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}"


def _punto(texto: str) -> str:
    texto = texto.strip()
    return texto if texto.endswith((".", "?", "!")) else f"{texto}."


def _anio(fecha: date | None) -> str:
    return str(fecha.year) if fecha else SIN_FECHA


def referencia_texto(
    titulo: str,
    autor: str | None,
    fecha_publicacion: date | None,
    sitio: str,
    url: str,
    doi: str | None,
    fecha_consulta: datetime,
) -> str:
    """Sin autor, el título ocupa la posición del autor; sin fecha, se indica la fecha de consulta."""
    enlace = f"{PREFIJO_DOI}{doi}" if doi else url
    recuperado = (
        "" if fecha_publicacion else f"Recuperado el {_fecha_larga(fecha_consulta.date())}, de "
    )
    fecha = f"({_anio(fecha_publicacion)})."
    if autor:
        return f"{_punto(autor)} {fecha} {_punto(titulo)} {_punto(sitio)} {recuperado}{enlace}"
    return f"{_punto(titulo)} {fecha} {_punto(sitio)} {recuperado}{enlace}"


def referencia_imagen(
    titulo: str, autor: str | None, proveedor: str, url_origen: str, licencia: str | None
) -> str:
    sujeto = _punto(autor) if autor else ""
    texto = f"{sujeto} ({SIN_FECHA}). {titulo} [Imagen]. {_punto(proveedor)} {url_origen}".strip()
    return f"{texto}. Licencia {licencia}." if licencia else texto


def referencia_video(titulo: str, canal: str, url: str) -> str:
    return f"{_punto(canal)} ({SIN_FECHA}). {titulo} [Video]. YouTube. {url}"


def referencia_ilustracion_ia(modelo: str, fecha: datetime) -> str:
    return f"Ilustración generada por IA con {modelo}; solicitada el {_fecha_larga(fecha.date())}."


def referencia_diagrama() -> str:
    return "Diagrama elaborado por TutorIA a partir de las fuentes citadas."
