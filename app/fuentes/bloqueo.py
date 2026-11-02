"""Fuentes de texto excluidas por diseño: sitios que cualquier persona puede editar o publicar
sin revisión editorial. La lista base vive en el código y la configuración solo puede ampliarla
(`FUENTES_DOMINIOS_BLOQUEADOS`). Wikimedia Commons se usa únicamente como banco de imágenes."""

import unicodedata
from collections.abc import Collection, Iterable
from typing import Protocol, TypeVar
from urllib.parse import urlsplit

DOMINIOS_BLOQUEADOS_BASE: frozenset[str] = frozenset(
    {
        # Wikimedia (texto)
        "wikipedia.org",
        "wikibooks.org",
        "wikiversity.org",
        "wikiquote.org",
        "wikinews.org",
        "wiktionary.org",
        "wikisource.org",
        "wikivoyage.org",
        "wikidata.org",
        "mediawiki.org",
        "wikimedia.org",
        "wikimediafoundation.org",
        # Wikis y enciclopedias abiertas o derivadas
        "fandom.com",
        "wikia.com",
        "wikihow.com",
        "ecured.cu",
        "dbpedia.org",
        "wikiwand.com",
        "everipedia.org",
        # Contenido de usuarios, apuntes y redes sociales
        "quora.com",
        "brainly.lat",
        "brainly.com",
        "answers.yahoo.com",
        "reddit.com",
        "medium.com",
        "blogspot.com",
        "wordpress.com",
        "tumblr.com",
        "monografias.com",
        "rincondelvago.com",
        "buenastareas.com",
        "studocu.com",
        "coursehero.com",
        "scribd.com",
        "slideshare.net",
        "academia.edu",
        "facebook.com",
        "x.com",
        "twitter.com",
        "instagram.com",
        "tiktok.com",
        "youtube.com",
    }
)
PREFIJO_PUNYCODE = "xn--"
SEPARADOR_ESQUEMA = "://"
CORCHETES = "[]"


class ConUrl(Protocol):
    @property
    def url(self) -> str: ...


T = TypeVar("T", bound=ConUrl)


def _etiqueta_ascii(etiqueta: str) -> str:
    if etiqueta.isascii():
        return etiqueta
    return PREFIJO_PUNYCODE + etiqueta.encode("punycode").decode("ascii")


def normalizar_host(url_o_host: str) -> str | None:
    """Host en minúsculas, sin punto final y en punycode; None si la entrada no tiene host.
    Usa `hostname` de urllib: el usuario, la ruta y la consulta nunca cuentan como host."""
    # NFKC antes de parsear: así urlsplit no ve caracteres que se vuelvan "/", "@" o ":" y no
    # lanza ValueError. Los corchetes (IP literal o URL mal formada) nunca son una fuente válida.
    texto = unicodedata.normalize("NFKC", url_o_host or "").strip()
    if not texto or any(c in texto for c in CORCHETES):
        return None
    url = texto if SEPARADOR_ESQUEMA in texto else f"//{texto}"
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if not host:
        return None
    etiquetas = host.split(".")
    if not all(etiquetas):
        return None
    return ".".join(_etiqueta_ascii(e) for e in etiquetas)


def _coincide(host: str, dominio: str) -> bool:
    return host == dominio or host.endswith(f".{dominio}")


def es_dominio_bloqueado(url_o_host: str, adicionales: Iterable[str] = ()) -> bool:
    """True si el host es un dominio bloqueado o un subdominio suyo (nunca por subcadena).
    Una entrada inválida o sin host se trata como bloqueada."""
    host = normalizar_host(url_o_host)
    if host is None:
        return True
    extra = {d for d in (normalizar_host(a) for a in adicionales) if d}
    return any(_coincide(host, d) for d in DOMINIOS_BLOQUEADOS_BASE | extra)


def sin_bloqueadas(fuentes: Iterable[T], adicionales: Collection[str] = ()) -> list[T]:
    """Descarta las fuentes leídas (de la BD o de un adaptador) cuyo dominio está bloqueado."""
    return [f for f in fuentes if not es_dominio_bloqueado(f.url, adicionales)]
