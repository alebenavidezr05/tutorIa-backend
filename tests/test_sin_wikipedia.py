"""Ningún dominio bloqueado de texto aparece en el código, los datos, la configuración de ejemplo
ni la documentación, salvo donde se declara como excluido (§1.9)."""

import re
from pathlib import Path

from app.fuentes.bloqueo import DOMINIOS_BLOQUEADOS_BASE

RAIZ = Path(__file__).resolve().parents[1]
ESTA_PRUEBA = Path(__file__).resolve()
LISTA_BASE = RAIZ / "app" / "fuentes" / "bloqueo.py"
DOCS_FUENTES = RAIZ / "docs" / "fuentes.md"
# Secciones de docs/fuentes.md que mencionan dominios bloqueados a propósito.
SECCION_EXCLUIDAS = "## Fuentes excluidas por diseño"
SECCION_IMAGENES = "## Imágenes"
WIKIMEDIA = "wikimedia.org"
# Wikimedia Commons solo como banco de imágenes: su configuración y su adaptador.
COMMONS_PERMITIDO = ("app/imagenes/", ".env.example")
# Los videos incrustables siguen su propio flujo (§12.5 del diseño): no son fuente de texto.
YOUTUBE = "youtube.com"
YOUTUBE_PERMITIDO = ("app/videos/", "app/validators/youtube.py")
EXTENSIONES = {".py", ".json", ".md", ".txt", ".example", ".toml", ".yml", ".yaml", ".env"}

PATRON = re.compile(
    r"(?<![a-z0-9-])(?:[a-z0-9-]+\.)*("
    + "|".join(re.escape(d) for d in sorted(DOMINIOS_BLOQUEADOS_BASE, key=len, reverse=True))
    + r")(?![a-z0-9-])",
    re.IGNORECASE,
)


def _archivos() -> list[Path]:
    carpetas = [RAIZ / "app", RAIZ / "data", RAIZ / "docs", RAIZ / "tests" / "fixtures"]
    encontrados = [p for c in carpetas if c.exists() for p in c.rglob("*") if p.is_file()]
    return [
        p
        for p in [*encontrados, RAIZ / ".env.example"]
        if p.suffix in EXTENSIONES or p.name == ".env.example"
    ]


def _texto_revisable(ruta: Path) -> str:
    texto = ruta.read_text(encoding="utf-8")
    if ruta != DOCS_FUENTES:
        return texto
    # Se quita la sección de exclusiones; en la de imágenes solo se tolera Wikimedia.
    secciones = re.split(r"(?m)^(?=## )", texto)
    revisables = []
    for seccion in secciones:
        if seccion.startswith(SECCION_EXCLUIDAS):
            continue
        if seccion.startswith(SECCION_IMAGENES):
            seccion = re.sub(r"(?:[a-z0-9-]+\.)*wikimedia\.org", "", seccion)
        revisables.append(seccion)
    return "".join(revisables)


def _permitido(relativa: str, dominio: str) -> bool:
    if dominio == WIKIMEDIA:
        return relativa.startswith(COMMONS_PERMITIDO)
    if dominio == YOUTUBE:
        return relativa.startswith(YOUTUBE_PERMITIDO)
    return False


def test_ningun_dominio_bloqueado_fuera_de_la_lista_base() -> None:
    hallazgos = []
    for ruta in _archivos():
        if ruta.resolve() in {ESTA_PRUEBA, LISTA_BASE}:
            continue
        relativa = ruta.relative_to(RAIZ).as_posix()
        for numero, linea in enumerate(_texto_revisable(ruta).splitlines(), start=1):
            for coincidencia in PATRON.finditer(linea):
                if not _permitido(relativa, coincidencia.group(1).lower()):
                    hallazgos.append(f"{relativa}:{numero}: {coincidencia.group(0)}")
    assert not hallazgos, "Dominios bloqueados fuera de lugar:\n" + "\n".join(hallazgos)


def test_commons_solo_en_la_configuracion_de_imagenes() -> None:
    linea = next(
        linea
        for linea in (RAIZ / ".env.example").read_text(encoding="utf-8").splitlines()
        if WIKIMEDIA in linea
    )
    assert linea.startswith("IMAGENES_PROVEEDORES=")


def test_la_prueba_detecta_un_dominio_bloqueado() -> None:
    assert PATRON.search("base_url=https://es.wikipedia.org/w/api.php")
    assert not PATRON.search("https://notwikipedia.org y https://medlineplus.gov")
