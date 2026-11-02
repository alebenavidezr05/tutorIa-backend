"""Carga fuentes revisadas por el equipo desde un JSON (ver data/fuentes_curadas.ejemplo.json).

Uso: python -m app.scripts.cargar_fuentes_curadas ruta.json
"""

import argparse
import json
import sys
from collections.abc import Collection
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.core.config import get_settings
from app.core.tiempo import ahora_utc
from app.crypto.indice_ciego import sha256_hex
from app.fuentes.base import AUTORIDAD_PISO
from app.fuentes.bloqueo import es_dominio_bloqueado
from app.models.enums import CategoriaFuente, TipoFuente
from app.models.fuente import Fuente
from app.scripts._comun import servicios_de_script

# Una fuente curada vale mientras una persona no la retire: se renueva cada carga.
DIAS_VIGENCIA_CURADA = 3650


class FuenteCurada(BaseModel):
    titulo: str = Field(max_length=300)
    autor: str | None = Field(default=None, max_length=200)
    sitio: str = Field(max_length=100)
    url: HttpUrl
    extracto: str = Field(max_length=1500)
    autoridad: int = Field(ge=AUTORIDAD_PISO, le=4)
    idioma: str = Field(default="es", min_length=2, max_length=2)
    licencia: str | None = Field(default=None, max_length=60)
    doi: str | None = Field(default=None, max_length=100)
    fecha_publicacion: date | None = None


def validar_curadas(
    datos: list[dict[str, Any]], dominios_bloqueados: Collection[str] = ()
) -> list[FuenteCurada]:
    """Rechaza el archivo completo si alguna fila apunta a un sitio editable por cualquiera."""
    curadas = [FuenteCurada.model_validate(d) for d in datos]
    filas = [
        f"{i} ({c.url.host})"
        for i, c in enumerate(curadas, start=1)
        if es_dominio_bloqueado(str(c.url), dominios_bloqueados)
    ]
    if filas:
        raise ValueError(
            "Fuentes curadas con dominio bloqueado (editable por cualquiera), filas: "
            + ", ".join(filas)
        )
    return curadas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ruta", type=Path)
    datos = json.loads(parser.parse_args().ruta.read_text(encoding="utf-8"))
    curadas = validar_curadas(datos, get_settings().fuentes_dominios_bloqueados)
    with servicios_de_script() as f:
        for curada in curadas:
            url = str(curada.url)
            existente = f.fuentes_repo.obtener_por_url_hash(sha256_hex(url))
            fuente = existente or Fuente(
                url=url, url_hash=sha256_hex(url), tipo=TipoFuente.TEXTO, proveedor="curada"
            )
            fuente.titulo, fuente.autor, fuente.sitio = curada.titulo, curada.autor, curada.sitio
            fuente.extracto, fuente.autoridad, fuente.idioma = (
                curada.extracto,
                curada.autoridad,
                curada.idioma,
            )
            fuente.licencia, fuente.doi, fuente.fecha_publicacion = (
                curada.licencia,
                curada.doi,
                curada.fecha_publicacion,
            )
            fuente.categoria, fuente.revisada_por_pares = CategoriaFuente.CURADA, None
            fuente.fecha_consulta = ahora_utc()
            fuente.fecha_expiracion = ahora_utc() + timedelta(days=DIAS_VIGENCIA_CURADA)
            if existente is None:
                f.fuentes_repo.agregar(fuente)
        f.uow.commit()
    print(f"{len(curadas)} fuentes curadas cargadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
