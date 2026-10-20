import re
import unicodedata

_PATRON_ESPACIOS = re.compile(r"\s+")
_PATRON_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# El nombre de la etiqueta va pegado a "<": así "a < b y b > c" no se confunde con HTML.
_PATRON_ETIQUETA_HTML = re.compile(r"</?[a-zA-Z][a-zA-Z0-9-]*(\s[^<>]*)?/?>")
_PATRON_URL = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_PATRON_MARKDOWN = re.compile(r"(\*\*|__|```|^#{1,6}\s|\[[^\]]+\]\([^)]+\))", re.MULTILINE)


def _quitar_caracteres_de_control(valor: str) -> str:
    return _PATRON_CONTROL.sub("", valor)


def _colapsar_espacios(valor: str) -> str:
    return _PATRON_ESPACIOS.sub(" ", valor).strip()


def normalizar_texto(valor: str) -> str:
    return _colapsar_espacios(_quitar_caracteres_de_control(valor))


def quitar_tildes(valor: str) -> str:
    descompuesto = unicodedata.normalize("NFD", valor)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar_para_comparar(valor: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados: base de todos los patrones."""
    return _colapsar_espacios(quitar_tildes(valor).lower())


def quitar_etiquetas(valor: str) -> str:
    return normalizar_texto(_PATRON_ETIQUETA_HTML.sub(" ", valor))


def truncar(valor: str, maximo: int) -> str:
    return valor if len(valor) <= maximo else valor[: maximo - 1].rstrip() + "…"


def limpiar_texto_externo(valor: str | None, maximo: int) -> str:
    """Texto que llega de un proveedor externo: sin etiquetas, sin saltos de línea y acotado."""
    return truncar(quitar_etiquetas(valor or ""), maximo)


def contiene_html(valor: str) -> bool:
    return bool(_PATRON_ETIQUETA_HTML.search(valor))


def contiene_url(valor: str) -> bool:
    return bool(_PATRON_URL.search(valor))


def contiene_markdown(valor: str) -> bool:
    return bool(_PATRON_MARKDOWN.search(valor))


def contiene_alguno(texto_normalizado: str, patrones: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(texto_normalizado) for p in patrones)


def compilar(*expresiones: str) -> tuple[re.Pattern[str], ...]:
    """Compila patrones escritos sin tildes, para aplicarlos sobre `normalizar_para_comparar`."""
    return tuple(re.compile(e) for e in expresiones)
