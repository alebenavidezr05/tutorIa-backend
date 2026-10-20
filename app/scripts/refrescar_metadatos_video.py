"""Re-consulta en YouTube los metadatos con más de VIDEO_METADATOS_MAX_DIAS (política de datos
almacenados). Un video que ya no existe o dejó de ser válido pasa a RETIRADO y no se muestra."""

import sys
from datetime import timedelta

from app.core.tiempo import ahora_utc
from app.models.enums import EstadoVideo
from app.scripts._comun import servicios_de_script
from app.scripts.cargar_videos import _motivo_rechazo


def main() -> int:
    with servicios_de_script() as f:
        s = f.settings
        vencidos = f.videos_repo.listar_con_metadatos_antes_de(
            ahora_utc() - timedelta(days=s.video_metadatos_max_dias)
        )
        actuales = (
            {
                m.youtube_id: m
                for m in f.contenedor.videos.obtener_metadatos([v.youtube_id for v in vencidos])
            }
            if vencidos
            else {}
        )
        for video in vencidos:
            metadatos = actuales.get(video.youtube_id)
            if (
                _motivo_rechazo(
                    metadatos, s.video_duracion_min_segundos, s.video_duracion_max_segundos
                )
                or metadatos is None
            ):
                video.estado = EstadoVideo.RETIRADO
                video.puntos_clave = None
                continue
            video.titulo, video.canal = metadatos.titulo[:300], metadatos.canal[:200]
            video.duracion_segundos, video.es_para_ninos = (
                metadatos.duracion_segundos,
                metadatos.es_para_ninos,
            )
            video.fecha_metadatos = ahora_utc()
        f.uow.commit()
    print(f"{len(vencidos)} videos revisados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
