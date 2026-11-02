"""MedlinePlus en español (Biblioteca Nacional de Medicina de EE. UU.): servicio web de temas de
salud. Los resúmenes de los temas de salud son de dominio público (obra del gobierno federal) y
deben atribuirse a MedlinePlus. Límite del servicio: 85 peticiones por minuto por IP."""

from typing import Any
from xml.etree import ElementTree

import httpx

from app.core.config import ConfigProveedor
from app.fuentes.adaptadores.http import obtener_xml
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.models.enums import CategoriaFuente
from app.validators.texto import quitar_etiquetas

BASE_DATOS_POR_IDIOMA = {"es": "healthTopicsSpanish", "en": "healthTopics"}
SITIO = "MedlinePlus, Biblioteca Nacional de Medicina de EE. UU."
LICENCIA = "Dominio público"
ESQUEMA_SEGURO = "https://"


def _campos(documento: ElementTree.Element) -> dict[str, str]:
    """Primer valor de cada `content name=...`, sin el resaltado HTML de la búsqueda."""
    campos: dict[str, str] = {}
    for contenido in documento.findall("content"):
        nombre = contenido.get("name", "")
        campos.setdefault(nombre, quitar_etiquetas("".join(contenido.itertext())))
    return campos


class MedlinePlusFuentesClient(FuentesClient):
    def __init__(self, config: ConfigProveedor, cliente: httpx.Client) -> None:
        super().__init__(config.id, CategoriaFuente(config.categoria), config.autoridad)
        self._config = config
        self._http = cliente

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        idioma_busqueda = idioma if idioma in BASE_DATOS_POR_IDIOMA else "es"
        parametros: dict[str, Any] = {
            "db": BASE_DATOS_POR_IDIOMA[idioma_busqueda],
            "term": consulta,
            "retmax": limite,
            "tool": self._config.parametros.get("tool", "tutoria"),
        }
        raiz = obtener_xml(self._http, self._config.base_url, parametros, self.proveedor)
        documentos = raiz.findall("./list/document")
        candidatas = [self._candidata(d, idioma_busqueda) for d in documentos]
        return [c for c in candidatas if c.extracto and c.url.startswith(ESQUEMA_SEGURO)]

    def cerrar(self) -> None:
        self._http.close()

    def _candidata(self, documento: ElementTree.Element, idioma: str) -> FuenteCandidata:
        campos = _campos(documento)
        return FuenteCandidata(
            titulo=campos.get("title", ""),
            autor=campos.get("organizationName") or "Biblioteca Nacional de Medicina",
            sitio=SITIO,
            url=documento.get("url", ""),
            extracto=campos.get("FullSummary") or campos.get("snippet", ""),
            categoria=self.categoria,
            autoridad=self.autoridad_base(),
            proveedor=self.proveedor,
            idioma=idioma,
            licencia=LICENCIA,
            revisada_por_pares=None,
        )
