"""Portales de datos abiertos de gobierno con API CKAN (`package_search`)."""

from datetime import date
from typing import Any

import httpx

from app.core.config import ConfigProveedor
from app.fuentes.adaptadores.http import obtener_json
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.models.enums import CategoriaFuente

LONGITUD_FECHA_ISO = 10


def _fecha(valor: str | None) -> date | None:
    return date.fromisoformat(valor[:LONGITUD_FECHA_ISO]) if valor else None


class CkanFuentesClient(FuentesClient):
    def __init__(self, config: ConfigProveedor, cliente: httpx.Client) -> None:
        super().__init__(config.id, CategoriaFuente(config.categoria), config.autoridad)
        self._config = config
        self._http = cliente
        self._url_dataset = config.parametros.get("url_dataset", "")
        self._sitio = config.parametros.get("sitio", config.id)

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        parametros = {"q": consulta, "rows": limite}
        datos = obtener_json(self._http, self._config.base_url, parametros, self.proveedor)
        paquetes = (datos.get("result") or {}).get("results", [])
        return [self._candidata(p, idioma) for p in paquetes if p.get("notes")]

    def cerrar(self) -> None:
        self._http.close()

    def _candidata(self, paquete: dict[str, Any], idioma: str) -> FuenteCandidata:
        organizacion = (paquete.get("organization") or {}).get("title")
        return FuenteCandidata(
            titulo=paquete.get("title") or paquete.get("name", ""),
            autor=organizacion,
            sitio=self._sitio,
            url=f"{self._url_dataset}{paquete.get('name', '')}",
            extracto=paquete.get("notes", ""),
            categoria=self.categoria,
            autoridad=self.autoridad_base(),
            proveedor=self.proveedor,
            idioma=idioma,
            fecha_publicacion=_fecha(paquete.get("metadata_modified")),
            licencia=paquete.get("license_title"),
            revisada_por_pares=None,
        )
