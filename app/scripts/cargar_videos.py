"""Alta o revisión de videos curados desde un JSON, validados con la YouTube Data API.

Uso: python -m app.scripts.cargar_videos ruta.json   (ver data/videos_curados.ejemplo.json)
Un video solo queda APROBADO si dura entre el mínimo y el máximo, es incrustable y no está
marcado como contenido para niños (madeForKids).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.tiempo import ahora_utc
from app.models.enums import EstadoVideo
from app.models.video_curado import VideoCurado
from app.scripts._comun import servicios_de_script
from app.services.videos.video_service import clave_tema
from app.validators.youtube import validar_youtube_id
from app.videos.base import MetadatosVideo

MAX_PUNTOS_CLAVE = 8


class VideoACargar(BaseModel):
    youtube_id: str
    tema: str = Field(min_length=3, max_length=100)
    puntos_clave: list[str] = Field(default_factory=list, max_length=MAX_PUNTOS_CLAVE)
    referencias_revision: list[dict[str, Any]] = Field(default_factory=list)
    revisado_por: str = Field(min_length=2, max_length=100)


def _motivo_rechazo(metadatos: MetadatosVideo | None, minimo: int, maximo: int) -> str | None:
    if metadatos is None:
        return "no existe o no se pudo consultar"
    if not minimo <= metadatos.duracion_segundos <= maximo:
        return f"duración fuera de rango ({metadatos.duracion_segundos} s)"
    if not metadatos.embeddable:
        return "no se puede incrustar"
    if metadatos.es_para_ninos:
        return "marcado como contenido para niños"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ruta", type=Path)
    videos = [
        VideoACargar.model_validate(d)
        for d in json.loads(parser.parse_args().ruta.read_text(encoding="utf-8"))
    ]
    with servicios_de_script() as f:
        s = f.settings
        consultados = {
            m.youtube_id: m
            for m in f.contenedor.videos.obtener_metadatos(
                [validar_youtube_id(v.youtube_id) for v in videos]
            )
        }
        for video in videos:
            metadatos = consultados.get(video.youtube_id)
            motivo = _motivo_rechazo(
                metadatos, s.video_duracion_min_segundos, s.video_duracion_max_segundos
            )
            if motivo or metadatos is None:
                print(f"[RECHAZADO] {video.youtube_id}: {motivo}")
                continue
            fila = f.videos_repo.obtener_por_youtube_id(video.youtube_id) or f.videos_repo.agregar(
                VideoCurado(
                    youtube_id=video.youtube_id,
                    fecha_creacion=ahora_utc(),
                    **_campos(video, metadatos),
                )
            )
            for campo, valor in _campos(video, metadatos).items():
                setattr(fila, campo, valor)
            print(f"[APROBADO] {video.youtube_id}: {metadatos.titulo}")
        f.uow.commit()
    return 0


def _campos(video: VideoACargar, metadatos: MetadatosVideo) -> dict[str, Any]:
    ahora = ahora_utc()
    return {
        "tema_clave": clave_tema(video.tema),
        "titulo": metadatos.titulo[:300],
        "canal": metadatos.canal[:200],
        "id_canal": metadatos.id_canal[:40],
        "duracion_segundos": metadatos.duracion_segundos,
        "idioma": metadatos.idioma or "es",
        "es_para_ninos": metadatos.es_para_ninos,
        "estado": EstadoVideo.APROBADO,
        "puntos_clave": video.puntos_clave,
        "referencias_revision": video.referencias_revision,
        "revisado_por": video.revisado_por,
        "fecha_revision": ahora,
        "fecha_metadatos": ahora,
    }


if __name__ == "__main__":
    sys.exit(main())
