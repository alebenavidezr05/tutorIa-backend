"""Colecciones de museos con API JSON e imágenes IIIF (implementado: Art Institute of Chicago).

Solo se aceptan obras marcadas `is_public_domain`; las demás nunca se devuelven.
"""

from typing import Any

import httpx

from app.core.config import ConfigProveedor
from app.imagenes.adaptadores.http import obtener_json
from app.imagenes.base import ImagenCandidata, ImagenesClient
from app.models.enums import CategoriaImagen

CAMPOS = "id,title,artist_display,is_public_domain,image_id,thumbnail,date_display"
ANCHO_IIIF = 843
PLANTILLA_IIIF = "{iiif}/{image_id}/full/{ancho},/0/default.jpg"
PLANTILLA_PAGINA = "{sitio}/artworks/{id}"
LICENCIA_DOMINIO_PUBLICO = "Public domain"
MIME_JPEG = "image/jpeg"


class IiifMuseoImagenesClient(ImagenesClient):
    def __init__(self, config: ConfigProveedor, cliente: httpx.Client) -> None:
        super().__init__(config.id, CategoriaImagen(config.categoria), config.dominios)
        self._config = config
        self._http = cliente

    def buscar(self, consulta: str, limite: int) -> list[ImagenCandidata]:
        parametros = {"q": consulta, "limit": limite, "fields": CAMPOS}
        datos = obtener_json(self._http, self._config.base_url, parametros, self.proveedor)
        configuracion = datos.get("config") or {}
        obras = [
            o for o in datos.get("data", []) if o.get("is_public_domain") and o.get("image_id")
        ]
        return [self._candidata(o, configuracion) for o in obras]

    def cerrar(self) -> None:
        self._http.close()

    def _candidata(self, obra: dict[str, Any], configuracion: dict[str, Any]) -> ImagenCandidata:
        miniatura = obra.get("thumbnail") or {}
        ancho_original = int(miniatura.get("width") or ANCHO_IIIF)
        alto_original = int(miniatura.get("height") or ANCHO_IIIF)
        return ImagenCandidata(
            titulo=obra.get("title") or "",
            descripcion=miniatura.get("alt_text") or "",
            autor=(obra.get("artist_display") or "").split("\n")[0] or None,
            url_origen=PLANTILLA_PAGINA.format(
                sitio=configuracion.get("website_url", ""), id=obra["id"]
            ),
            url_archivo=PLANTILLA_IIIF.format(
                iiif=configuracion.get("iiif_url", ""), image_id=obra["image_id"], ancho=ANCHO_IIIF
            ),
            mime=MIME_JPEG,
            ancho=ANCHO_IIIF,
            alto=int(alto_original * ANCHO_IIIF / max(ancho_original, 1)),
            licencia=LICENCIA_DOMINIO_PUBLICO,
            url_licencia=None,
            categoria=self.categoria,
            proveedor=self.proveedor,
        )
