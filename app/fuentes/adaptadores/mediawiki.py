from datetime import date
from typing import Any

import httpx

from app.core.config import ConfigProveedor
from app.fuentes.adaptadores.http import obtener_json
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.models.enums import CategoriaFuente

# Licencia del texto de los proyectos Wikimedia según sus condiciones de uso (verificar al activar).
LICENCIA_WIKIMEDIA = "CC BY-SA 4.0"
LONGITUD_FECHA_ISO = 10


def _parametros_busqueda(consulta: str, limite: int) -> dict[str, Any]:
    return {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": consulta,
        "gsrlimit": limite,
        "gsrnamespace": "0",
        "prop": "extracts|info|revisions",
        "exintro": "1",
        "explaintext": "1",
        "exlimit": "max",
        "inprop": "url",
        "rvprop": "timestamp",
    }


def _fecha_revision(pagina: dict[str, Any]) -> date | None:
    revisiones = pagina.get("revisions") or []
    marca = revisiones[0].get("timestamp", "") if revisiones else ""
    return date.fromisoformat(marca[:LONGITUD_FECHA_ISO]) if marca else None


class MediaWikiFuentesClient(FuentesClient):
    """API tipo MediaWiki (enciclopedias y libros colaborativos): búsqueda + extracto de introducción."""

    def __init__(self, config: ConfigProveedor, cliente: httpx.Client) -> None:
        super().__init__(config.id, CategoriaFuente(config.categoria), config.autoridad)
        self._config = config
        self._http = cliente
        self._sitio = config.parametros.get("sitio", config.id)

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        datos = obtener_json(
            self._http,
            self._config.base_url,
            _parametros_busqueda(consulta, limite),
            self.proveedor,
        )
        paginas = sorted(datos.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0))
        return [self._candidata(p, idioma) for p in paginas if p.get("extract")]

    def cerrar(self) -> None:
        self._http.close()

    def _candidata(self, pagina: dict[str, Any], idioma: str) -> FuenteCandidata:
        return FuenteCandidata(
            titulo=pagina.get("title", ""),
            autor=None,
            sitio=self._sitio,
            url=pagina.get("fullurl") or pagina.get("canonicalurl", ""),
            extracto=pagina.get("extract", ""),
            categoria=self.categoria,
            autoridad=self.autoridad_base(),
            proveedor=self.proveedor,
            idioma=idioma,
            fecha_publicacion=_fecha_revision(pagina),
            licencia=self._config.parametros.get("licencia", LICENCIA_WIKIMEDIA),
            revisada_por_pares=False,
        )
