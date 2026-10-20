import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select

from app.models.enums import EstadoTrabajoVisual
from app.models.recurso_visual import RecursoVisual
from app.models.trabajo_visual import TrabajoVisual
from app.repositories.base import RepositorioBase


class RecursoVisualRepository(RepositorioBase[RecursoVisual]):
    modelo = RecursoVisual

    def obtener_por_clave_cache(self, clave_cache: str) -> RecursoVisual | None:
        consulta = select(RecursoVisual).where(RecursoVisual.clave_cache == clave_cache)
        return self._session.scalar(consulta)

    def listar_por_ids(self, ids: Collection[uuid.UUID]) -> list[RecursoVisual]:
        consulta = select(RecursoVisual).where(RecursoVisual.id_recurso.in_(ids))
        return list(self._session.scalars(consulta))

    def listar_vencidos(self, ahora: datetime) -> list[RecursoVisual]:
        consulta = select(RecursoVisual).where(RecursoVisual.fecha_expiracion < ahora)
        return list(self._session.scalars(consulta))


class TrabajoVisualRepository(RepositorioBase[TrabajoVisual]):
    modelo = TrabajoVisual

    def obtener_por_mensaje(self, id_mensaje: uuid.UUID) -> TrabajoVisual | None:
        return self._session.scalar(
            select(TrabajoVisual).where(TrabajoVisual.id_mensaje == id_mensaje)
        )

    def listar_por_mensajes(self, ids_mensajes: Collection[uuid.UUID]) -> list[TrabajoVisual]:
        consulta = select(TrabajoVisual).where(TrabajoVisual.id_mensaje.in_(ids_mensajes))
        return list(self._session.scalars(consulta))

    def existe_para_usuario(self, id_recurso: uuid.UUID, id_usuario: uuid.UUID) -> bool:
        consulta = select(TrabajoVisual.id_trabajo).where(
            TrabajoVisual.id_recurso == id_recurso, TrabajoVisual.id_usuario == id_usuario
        )
        return self._session.scalar(consulta.limit(1)) is not None

    def listar_procesando_antes_de(self, instante: datetime) -> list[TrabajoVisual]:
        consulta = select(TrabajoVisual).where(
            TrabajoVisual.estado.in_(
                [EstadoTrabajoVisual.PROCESANDO, EstadoTrabajoVisual.PENDIENTE]
            ),
            TrabajoVisual.fecha_creacion < instante,
        )
        return list(self._session.scalars(consulta))
