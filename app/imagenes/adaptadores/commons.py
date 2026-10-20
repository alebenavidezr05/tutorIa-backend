"""Bancos de medios con API tipo MediaWiki (Wikimedia Commons): licencia y autor por archivo."""

import re
from typing import Any

import httpx

from app.core.config import ConfigProveedor
from app.imagenes.adaptadores.http import obtener_json
from app.imagenes.base import ImagenCandidata, ImagenesClient
from app.models.enums import CategoriaImagen

ANCHO_MINIATURA = 800
ESPACIO_ARCHIVOS = "6"
CAMPOS_METADATOS = "LicenseShortName|LicenseUrl|Artist|ImageDescription|ObjectName"
_PATRON_ETIQUETA = re.compile(r"<[^>]+>")
PREFIJO_ARCHIVO = "File:"


def _texto_meta(metadatos: dict[str, Any], campo: str) -> str:
    valor = (metadatos.get(campo) or {}).get("value", "")
    return _PATRON_ETIQUETA.sub("", str(valor)).strip()


def _parametros(consulta: str, limite: int) -> dict[str, Any]:
    return {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": consulta,
        "gsrnamespace": ESPACIO_ARCHIVOS,
        "gsrlimit": limite,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": ANCHO_MINIATURA,
        "iiextmetadatafilter": CAMPOS_METADATOS,
    }


class CommonsImagenesClient(ImagenesClient):
    def __init__(self, config: ConfigProveedor, cliente: httpx.Client) -> None:
        super().__init__(config.id, CategoriaImagen(config.categoria), config.dominios)
        self._config = config
        self._http = cliente

    def buscar(self, consulta: str, limite: int) -> list[ImagenCandidata]:
        datos = obtener_json(
            self._http, self._config.base_url, _parametros(consulta, limite), self.proveedor
        )
        paginas = sorted(datos.get("query", {}).get("pages", []), key=lambda p: p.get("index", 0))
        return [self._candidata(p) for p in paginas if p.get("imageinfo")]

    def cerrar(self) -> None:
        self._http.close()

    def _candidata(self, pagina: dict[str, Any]) -> ImagenCandidata:
        info = pagina["imageinfo"][0]
        metadatos = info.get("extmetadata") or {}
        titulo = _texto_meta(metadatos, "ObjectName") or pagina.get("title", "").removeprefix(
            PREFIJO_ARCHIVO
        )
        return ImagenCandidata(
            titulo=titulo,
            descripcion=_texto_meta(metadatos, "ImageDescription"),
            autor=_texto_meta(metadatos, "Artist") or None,
            url_origen=info.get("descriptionurl", ""),
            # La miniatura raster sirve también para SVG: nunca se descarga el SVG original.
            url_archivo=info.get("thumburl") or info.get("url", ""),
            mime=info.get("mime", ""),
            ancho=int(info.get("thumbwidth") or info.get("width") or 0),
            alto=int(info.get("thumbheight") or info.get("height") or 0),
            licencia=_texto_meta(metadatos, "LicenseShortName"),
            url_licencia=_texto_meta(metadatos, "LicenseUrl") or None,
            categoria=self.categoria,
            proveedor=self.proveedor,
        )
