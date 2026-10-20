from collections.abc import Collection
from urllib.parse import urlsplit


def _origen_de_url(url: str) -> str:
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}" if partes.scheme and partes.netloc else ""


def _normalizar(origen: str) -> str:
    return origen.strip().rstrip("/").lower()


def validar_origen(origen: str | None, referer: str | None, permitidos: Collection[str]) -> bool:
    """Usa `Origin`; si falta, el origen del `Referer`. Sin ninguno de los dos, no se permite."""
    candidato = origen or _origen_de_url(referer or "")
    return bool(candidato) and _normalizar(candidato) in {_normalizar(p) for p in permitidos}
