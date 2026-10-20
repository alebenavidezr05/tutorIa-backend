import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select

from app.models.enums import EstadoVideo
from app.models.video_curado import VideoCurado
from app.repositories.base import RepositorioBase


class VideoCuradoRepository(RepositorioBase[VideoCurado]):
    modelo = VideoCurado

    def listar_aprobados_por_tema(self, tema_clave: str, limite: int) -> list[VideoCurado]:
        consulta = (
            select(VideoCurado)
            .where(VideoCurado.tema_clave == tema_clave, VideoCurado.estado == EstadoVideo.APROBADO)
            .order_by(VideoCurado.fecha_revision.desc())
            .limit(limite)
        )
        return list(self._session.scalars(consulta))

    def obtener_por_ids(self, ids: Collection[uuid.UUID]) -> list[VideoCurado]:
        return list(self._session.scalars(select(VideoCurado).where(VideoCurado.id_video.in_(ids))))

    def obtener_por_youtube_id(self, youtube_id: str) -> VideoCurado | None:
        return self._session.scalar(select(VideoCurado).where(VideoCurado.youtube_id == youtube_id))

    def listar_con_metadatos_antes_de(self, instante: datetime) -> list[VideoCurado]:
        consulta = select(VideoCurado).where(
            VideoCurado.fecha_metadatos < instante, VideoCurado.estado != EstadoVideo.RETIRADO
        )
        return list(self._session.scalars(consulta))
