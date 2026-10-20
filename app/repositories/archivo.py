import uuid
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select

from app.models.archivo_adjunto import ArchivoAdjunto
from app.models.enums import EstadoArchivo
from app.repositories.base import RepositorioBase


class ArchivoRepository(RepositorioBase[ArchivoAdjunto]):
    modelo = ArchivoAdjunto

    def listar_vencidos(self, ahora: datetime) -> list[ArchivoAdjunto]:
        consulta = select(ArchivoAdjunto).where(ArchivoAdjunto.fecha_expiracion < ahora)
        return list(self._session.scalars(consulta))

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[ArchivoAdjunto]:
        consulta = select(ArchivoAdjunto).where(
            ArchivoAdjunto.id_usuario == id_usuario,
            ArchivoAdjunto.estado != EstadoArchivo.ELIMINADO,
        )
        return list(self._session.scalars(consulta))

    def listar_por_mensajes(self, ids_mensajes: Collection[uuid.UUID]) -> list[ArchivoAdjunto]:
        consulta = select(ArchivoAdjunto).where(ArchivoAdjunto.id_mensaje.in_(ids_mensajes))
        return list(self._session.scalars(consulta))

    def listar_por_actividades(
        self, ids_actividades: Collection[uuid.UUID]
    ) -> list[ArchivoAdjunto]:
        consulta = select(ArchivoAdjunto).where(ArchivoAdjunto.id_actividad.in_(ids_actividades))
        return list(self._session.scalars(consulta))

    def listar_por_contexto(self, id_contexto: uuid.UUID) -> list[ArchivoAdjunto]:
        consulta = select(ArchivoAdjunto).where(ArchivoAdjunto.id_contexto == id_contexto)
        return list(self._session.scalars(consulta))
