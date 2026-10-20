import json
import uuid
from datetime import timedelta
from typing import Any

from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.models.enums import CampoUso, EstadoVideo
from app.models.video_curado import VideoCurado
from app.repositories.video import VideoCuradoRepository
from app.services.uso_service import UsoService
from app.validators.texto import normalizar_para_comparar
from app.validators.youtube import construir_url_video
from app.videos.base import MetadatosVideo, VideosClient

SEGUNDOS_POR_MINUTO = 60
SIN_RESULTADOS = "Sin resultados."
TIPO_VIDEO = "video"
MAX_TEMA_CLAVE = 100
FACTOR_CANDIDATOS = 5


def clave_tema(tema: str) -> str:
    return normalizar_para_comparar(tema)[:MAX_TEMA_CLAVE]


class VideoService:
    """Videos revisados por personas (fuente de verdad: `video_curado`). El sistema no ve el video:
    solo conoce título, canal, duración y los puntos clave aprobados."""

    def __init__(
        self,
        videos: VideoCuradoRepository,
        cliente: VideosClient,
        uso: UsoService,
        settings: Settings,
    ) -> None:
        self._videos = videos
        self._cliente = cliente
        self._uso = uso
        self._settings = settings
        self._pendientes: list[VideoCurado] = []

    def buscar_para_herramienta(
        self, tema: str, id_usuario: uuid.UUID
    ) -> tuple[str, list[VideoCurado]]:
        if self._uso.restante(id_usuario, CampoUso.BUSQUEDAS_VIDEO) <= 0:
            return SIN_RESULTADOS, []
        limite = self._settings.videos_max_resultados
        # Se piden más candidatos de los necesarios: algunos se descartan por vigencia o duración.
        candidatos = self._videos.listar_aprobados_por_tema(
            clave_tema(tema), limite * FACTOR_CANDIDATOS
        )
        videos = [v for v in candidatos if self.es_mostrable(v)][:limite]
        if self._settings.videos_busqueda_dinamica and len(videos) < limite:
            videos += self._buscar_dinamicos(tema, limite - len(videos))
        return (
            json.dumps([self._resumen(v) for v in videos], ensure_ascii=False)
            if videos
            else SIN_RESULTADOS
        ), videos

    def persistir_pendientes(self) -> None:
        self._videos.agregar_varios(self._pendientes)
        self._pendientes.clear()

    def es_mostrable(self, video: VideoCurado) -> bool:
        vigente = video.fecha_metadatos >= ahora_utc() - timedelta(
            days=self._settings.video_metadatos_max_dias
        )
        return (
            video.estado != EstadoVideo.RETIRADO
            and vigente
            and not video.es_para_ninos
            and self._duracion_valida(video.duracion_segundos)
        )

    def hidratar(self, bloques: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Completa los bloques `video`; un video retirado o con metadatos vencidos no se muestra."""
        ids = {uuid.UUID(str(b["id_video"])) for b in bloques if b.get("tipo") == TIPO_VIDEO}
        videos = {v.id_video: v for v in self._videos.obtener_por_ids(ids) if self.es_mostrable(v)}
        return [self._hidratar_bloque(b, videos) for b in bloques if self._visible(b, videos)]

    def _visible(self, bloque: dict[str, Any], videos: dict[uuid.UUID, VideoCurado]) -> bool:
        return bloque.get("tipo") != TIPO_VIDEO or uuid.UUID(str(bloque["id_video"])) in videos

    @staticmethod
    def _hidratar_bloque(
        bloque: dict[str, Any], videos: dict[uuid.UUID, VideoCurado]
    ) -> dict[str, Any]:
        if bloque.get("tipo") != TIPO_VIDEO:
            return bloque
        video = videos[uuid.UUID(str(bloque["id_video"]))]
        return {
            **bloque,
            "youtube_id": video.youtube_id,
            "titulo": video.titulo,
            "canal": video.canal,
            "duracion_segundos": video.duracion_segundos,
            "url": construir_url_video(video.youtube_id),
            "verificado": video.estado == EstadoVideo.APROBADO,
        }

    def _duracion_valida(self, segundos: int) -> bool:
        return (
            self._settings.video_duracion_min_segundos
            <= segundos
            <= self._settings.video_duracion_max_segundos
        )

    def _buscar_dinamicos(self, tema: str, limite: int) -> list[VideoCurado]:
        confiables = set(self._settings.videos_canales_confiables)
        hallados = [
            m
            for m in self._cliente.buscar(tema, limite)
            if m.id_canal in confiables
            and m.embeddable
            and not m.es_para_ninos
            and self._duracion_valida(m.duracion_segundos)
        ]
        return [self._pendiente_revision(m, tema) for m in hallados]

    def _pendiente_revision(self, metadatos: MetadatosVideo, tema: str) -> VideoCurado:
        existente = self._videos.obtener_por_youtube_id(metadatos.youtube_id)
        if existente is not None:
            return existente
        ahora = ahora_utc()
        video = VideoCurado(
            id_video=uuid.uuid4(),
            youtube_id=metadatos.youtube_id,
            tema_clave=clave_tema(tema),
            titulo=metadatos.titulo[:300],
            canal=metadatos.canal[:200],
            id_canal=metadatos.id_canal[:40],
            duracion_segundos=metadatos.duracion_segundos,
            idioma=metadatos.idioma or "es",
            es_para_ninos=metadatos.es_para_ninos,
            estado=EstadoVideo.PENDIENTE_REVISION,
            fecha_metadatos=ahora,
            fecha_creacion=ahora,
        )
        self._pendientes.append(video)
        return video

    @staticmethod
    def _resumen(video: VideoCurado) -> dict[str, Any]:
        datos: dict[str, Any] = {
            "id_video": str(video.id_video),
            "titulo": video.titulo,
            "canal": video.canal,
            "duracion_min": round(video.duracion_segundos / SEGUNDOS_POR_MINUTO),
            "verificado": video.estado == EstadoVideo.APROBADO,
        }
        if video.puntos_clave:
            datos["puntos_clave"] = video.puntos_clave
        return datos
