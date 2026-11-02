import uuid
from collections.abc import Collection, Iterable

from app.exceptions.base import RecursoNoEncontradoError
from app.fuentes.bloqueo import sin_bloqueadas
from app.models.conversacion import Conversacion
from app.models.enums import RolMensaje, TipoRecursoVisual
from app.models.fuente import Fuente
from app.models.recurso_visual import RecursoVisual
from app.models.video_curado import VideoCurado
from app.repositories.conversacion import ConversacionRepository, MensajeRepository
from app.repositories.fuente import FuenteRepository
from app.repositories.video import VideoCuradoRepository
from app.repositories.visual import RecursoVisualRepository, TrabajoVisualRepository
from app.schemas.fuente import ReferenciaPublica
from app.services.fuentes import formato_apa
from app.validators.propiedad import validar_recurso_propio
from app.validators.youtube import construir_url_video

TIPOS_BLOQUE_VIDEO = {"video", "pregunta_resumen"}


class ReferenciasService:
    """Fuentes y referencias de todo lo que se mostró en una sesión: texto, imágenes, videos,
    ilustraciones IA y diagramas. El modelo nunca escribe una referencia ni una URL."""

    def __init__(
        self,
        conversaciones: ConversacionRepository,
        mensajes: MensajeRepository,
        fuentes: FuenteRepository,
        trabajos: TrabajoVisualRepository,
        recursos: RecursoVisualRepository,
        videos: VideoCuradoRepository,
        dominios_bloqueados: Collection[str] = (),
    ) -> None:
        self._conversaciones = conversaciones
        self._mensajes = mensajes
        self._fuentes = fuentes
        self._trabajos = trabajos
        self._recursos = recursos
        self._videos = videos
        self._dominios_bloqueados = dominios_bloqueados

    def de_conversacion(
        self, id_usuario: uuid.UUID, id_conversacion: uuid.UUID
    ) -> list[ReferenciaPublica]:
        conversacion = self._propia(id_usuario, id_conversacion)
        referencias = [
            *self._de_fuentes(self._fuentes_de(conversacion)),
            *self._de_recursos(self._recursos_de(conversacion)),
            *self._de_videos(self._videos_de(conversacion)),
        ]
        unicas = {r.texto_apa: r for r in referencias}
        return sorted(unicas.values(), key=lambda r: r.texto_apa.casefold())

    def _propia(self, id_usuario: uuid.UUID, id_conversacion: uuid.UUID) -> Conversacion:
        conversacion = self._conversaciones.obtener_por_id(id_conversacion)
        if conversacion is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(conversacion.id_usuario, id_usuario)
        return conversacion

    def _fuentes_de(self, conversacion: Conversacion) -> list[Fuente]:
        fuentes = self._fuentes.listar_por_conversacion(conversacion.id_conversacion)
        if conversacion.id_plan:
            fuentes += self._fuentes.listar_por_plan(conversacion.id_plan)
        # Una fuente de dominio bloqueado jamás aparece en las referencias, aunque esté guardada.
        return sin_bloqueadas(fuentes, self._dominios_bloqueados)

    def _recursos_de(self, conversacion: Conversacion) -> list[RecursoVisual]:
        ids_mensajes = [
            m.id_mensaje
            for m in self._mensajes.listar_por_conversacion(conversacion.id_conversacion)
        ]
        ids_recursos = [
            t.id_recurso for t in self._trabajos.listar_por_mensajes(ids_mensajes) if t.id_recurso
        ]
        return self._recursos.listar_por_ids(ids_recursos)

    def _videos_de(self, conversacion: Conversacion) -> list[VideoCurado]:
        ids = {
            uuid.UUID(str(b["id_video"]))
            for m in self._mensajes.listar_por_conversacion(conversacion.id_conversacion)
            if m.rol == RolMensaje.TUTOR
            for b in (m.bloques or [])
            if b.get("tipo") in TIPOS_BLOQUE_VIDEO
        }
        return self._videos.obtener_por_ids(ids)

    @staticmethod
    def _de_fuentes(fuentes: Iterable[Fuente]) -> list[ReferenciaPublica]:
        return [
            ReferenciaPublica(
                id_fuente=f.id_fuente,
                tipo=f.categoria.value,
                texto_apa=formato_apa.referencia_texto(
                    f.titulo, f.autor, f.fecha_publicacion, f.sitio, f.url, f.doi, f.fecha_consulta
                ),
                url=f"{formato_apa.PREFIJO_DOI}{f.doi}" if f.doi else f.url,
            )
            for f in fuentes
        ]

    @staticmethod
    def _de_recursos(recursos: Iterable[RecursoVisual]) -> list[ReferenciaPublica]:
        return [ReferenciasService._de_recurso(r) for r in recursos]

    @staticmethod
    def _de_recurso(recurso: RecursoVisual) -> ReferenciaPublica:
        if recurso.tipo == TipoRecursoVisual.IA:
            texto = formato_apa.referencia_ilustracion_ia(
                recurso.modelo_ia or "", recurso.fecha_creacion
            )
        elif recurso.tipo == TipoRecursoVisual.DIAGRAMA:
            texto = formato_apa.referencia_diagrama()
        else:
            texto = formato_apa.referencia_imagen(
                recurso.titulo,
                recurso.autor,
                recurso.proveedor or "",
                recurso.url_origen or "",
                recurso.licencia,
            )
        return ReferenciaPublica(
            id_recurso=recurso.id_recurso,
            tipo=recurso.tipo.value,
            texto_apa=texto,
            url=recurso.url_origen,
        )

    @staticmethod
    def _de_videos(videos: Iterable[VideoCurado]) -> list[ReferenciaPublica]:
        return [
            ReferenciaPublica(
                id_video=v.id_video,
                tipo="VIDEO",
                texto_apa=formato_apa.referencia_video(
                    v.titulo, v.canal, construir_url_video(v.youtube_id)
                ),
                url=construir_url_video(v.youtube_id),
            )
            for v in videos
        ]
