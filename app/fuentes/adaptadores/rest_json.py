"""Índices académicos con API REST/JSON. Implementado: OpenAlex (metadatos CC0, acceso abierto)."""

import threading
import time
from collections.abc import Callable
from datetime import date
from typing import Any

import httpx
from pydantic import SecretStr

from app.core.config import ConfigProveedor
from app.fuentes.adaptadores.http import PoliticaReintento, obtener_json, turno
from app.fuentes.base import FuenteCandidata, FuentesClient
from app.models.enums import CategoriaFuente

PREFIJO_DOI = "https://doi.org/"
CAMPOS_OPENALEX = (
    "id,doi,title,type,language,publication_date,authorships,primary_location,"
    "best_oa_location,abstract_inverted_index"
)
MAX_AUTORES = 3
AUTORIDAD_REVISADA_POR_PARES = 4
AUTORIDAD_TESIS = 3
AUTORIDAD_PREPRINT = 2
AUTORIDAD_SIN_DATOS_DE_REVISION = 3
TIPO_PREPRINT = "preprint"
TIPO_TESIS = "dissertation"
# Un 429 con reinicio de hasta estos segundos se espera y se reintenta una vez; uno más largo
# (presupuesto diario agotado) degrada de inmediato con las demás fuentes.
ESPERA_MAXIMA_429_SEGUNDOS = 3.0
ESPERA_5XX_SEGUNDOS = 1.0
ESPERA_TURNO_SEGUNDOS = 15.0
# Máximo una petición simultánea a OpenAlex por proceso: su límite es por segundo y por día.
_SEMAFORO_OPENALEX = threading.BoundedSemaphore(1)


def _resumen_desde_indice(indice: dict[str, list[int]] | None) -> str:
    """OpenAlex entrega el resumen como índice invertido (palabra -> posiciones)."""
    if not indice:
        return ""
    posiciones = sorted((pos, palabra) for palabra, lista in indice.items() for pos in lista)
    return " ".join(palabra for _, palabra in posiciones)


def _autores(obra: dict[str, Any]) -> str | None:
    nombres = [
        a.get("author", {}).get("display_name", "")
        for a in obra.get("authorships", [])[:MAX_AUTORES]
    ]
    nombres = [n for n in nombres if n]
    if not nombres:
        return None
    sufijo = " et al." if len(obra.get("authorships", [])) > MAX_AUTORES else ""
    return ", ".join(nombres) + sufijo


def _revision(obra: dict[str, Any]) -> tuple[int, bool | None]:
    tipo = obra.get("type")
    if tipo == TIPO_PREPRINT:
        return AUTORIDAD_PREPRINT, False
    if tipo == TIPO_TESIS:
        return AUTORIDAD_TESIS, None
    fuente = (obra.get("primary_location") or {}).get("source") or {}
    # Las revistas indexadas en DOAJ cumplen su criterio de revisión por pares o editorial.
    if fuente.get("is_in_doaj"):
        return AUTORIDAD_REVISADA_POR_PARES, True
    return AUTORIDAD_SIN_DATOS_DE_REVISION, None


def _fecha(valor: str | None) -> date | None:
    return date.fromisoformat(valor) if valor else None


class OpenAlexFuentesClient(FuentesClient):
    """La API key (OPENALEX_API_KEY, nunca dentro de FUENTES_PROVEEDORES) viaja en la cabecera
    Authorization, no en la URL, y no se registra en logs ni errores. OpenAlex retiró `mailto`."""

    def __init__(
        self,
        config: ConfigProveedor,
        cliente: httpx.Client,
        api_key: SecretStr | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(config.id, CategoriaFuente(config.categoria), config.autoridad)
        self._config = config
        self._http = cliente
        self._api_key = api_key
        self._politica = PoliticaReintento(ESPERA_MAXIMA_429_SEGUNDOS, ESPERA_5XX_SEGUNDOS, dormir)

    def buscar(self, consulta: str, idioma: str, limite: int) -> list[FuenteCandidata]:
        with turno(_SEMAFORO_OPENALEX, ESPERA_TURNO_SEGUNDOS, self.proveedor):
            datos = obtener_json(
                self._http,
                self._config.base_url,
                self._parametros(consulta, idioma, limite),
                self.proveedor,
                self._cabeceras(),
                self._politica,
            )
        candidatas = [self._candidata(o) for o in datos.get("results", [])]
        return [c for c in candidatas if c.extracto and c.url]

    def cerrar(self) -> None:
        self._http.close()

    def _cabeceras(self) -> dict[str, str] | None:
        if self._api_key is None or not self._api_key.get_secret_value():
            return None
        return {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}

    @staticmethod
    def _parametros(consulta: str, idioma: str, limite: int) -> dict[str, Any]:
        return {
            "search": consulta,
            "filter": f"language:{idioma},is_oa:true",
            "per_page": limite,
            "select": CAMPOS_OPENALEX,
        }

    def _candidata(self, obra: dict[str, Any]) -> FuenteCandidata:
        ubicacion = obra.get("primary_location") or {}
        acceso = obra.get("best_oa_location") or {}
        doi = (obra.get("doi") or "").removeprefix(PREFIJO_DOI) or None
        autoridad, revisada = _revision(obra)
        return FuenteCandidata(
            titulo=obra.get("title") or "",
            autor=_autores(obra),
            sitio=((ubicacion.get("source") or {}).get("display_name") or "OpenAlex")[:100],
            url=ubicacion.get("landing_page_url") or (f"{PREFIJO_DOI}{doi}" if doi else ""),
            extracto=_resumen_desde_indice(obra.get("abstract_inverted_index")),
            categoria=self.categoria,
            autoridad=min(autoridad, self._config.autoridad or autoridad),
            proveedor=self.proveedor,
            idioma=obra.get("language") or "",
            doi=doi,
            fecha_publicacion=_fecha(obra.get("publication_date")),
            licencia=acceso.get("license"),
            revisada_por_pares=revisada,
        )
