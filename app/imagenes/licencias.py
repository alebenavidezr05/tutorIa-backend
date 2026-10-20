"""Normalización de licencias de imágenes (funciones puras)."""

import re
import unicodedata
from collections.abc import Collection
from dataclasses import dataclass


@dataclass(frozen=True)
class LicenciaAbierta:
    codigo: str
    nombre: str
    requiere_atribucion: bool
    url: str


DOMINIO_PUBLICO = LicenciaAbierta(
    "PD", "Dominio público", False, "https://creativecommons.org/publicdomain/mark/1.0/"
)
CC0 = LicenciaAbierta("CC0", "CC0 1.0", False, "https://creativecommons.org/publicdomain/zero/1.0/")
CC_BY = LicenciaAbierta("CC-BY", "CC BY", True, "https://creativecommons.org/licenses/by/4.0/")
CC_BY_SA = LicenciaAbierta(
    "CC-BY-SA", "CC BY-SA", True, "https://creativecommons.org/licenses/by-sa/4.0/"
)
# NC y ND se excluyen: el producto tiene plan de pago y las imágenes se redimensionan.
_PATRON_EXCLUIDAS = re.compile(r"\b(nc|nd)\b|non.?commercial|no.?deriv")
_PATRON_VERSION = re.compile(r"(\d\.\d)")
_REGLAS = (
    (re.compile(r"publicdomain/zero|\bcc0\b|cc-zero"), CC0),
    (re.compile(r"publicdomain/mark|public domain|dominio publico|^pd\b|\bpd-"), DOMINIO_PUBLICO),
    (re.compile(r"by-sa|by sa|bysa"), CC_BY_SA),
    (re.compile(r"licenses/by/|cc[- ]by\b|cc-by-\d|^by\b"), CC_BY),
)


def _con_version(licencia: LicenciaAbierta, original: str) -> LicenciaAbierta:
    version = _PATRON_VERSION.search(original)
    if licencia.codigo in {"PD", "CC0"} or not version:
        return licencia
    return LicenciaAbierta(
        licencia.codigo,
        f"{licencia.nombre} {version.group(1)}",
        licencia.requiere_atribucion,
        licencia.url.replace("4.0", version.group(1)),
    )


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFD", texto)
    return "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn").lower().strip()


def normalizar_licencia(texto_o_uri: str | None) -> LicenciaAbierta | None:
    texto = _normalizar(texto_o_uri or "")
    if not texto or _PATRON_EXCLUIDAS.search(texto):
        return None
    for patron, licencia in _REGLAS:
        if patron.search(texto):
            return _con_version(licencia, texto)
    return None


def licencia_permitida(licencia: LicenciaAbierta | None, permitidas: Collection[str]) -> bool:
    return licencia is not None and licencia.codigo in permitidas
