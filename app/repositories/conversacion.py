import uuid
from datetime import datetime

from sqlalchemy import func, select

from app.models.conversacion import Conversacion
from app.models.enums import EstadoConversacion, RolMensaje, TipoEvento
from app.models.evento_aprendizaje import EventoAprendizaje
from app.models.mensaje import Mensaje
from app.models.perfil_aprendizaje import PerfilAprendizaje
from app.repositories.base import RepositorioBase


class ConversacionRepository(RepositorioBase[Conversacion]):
    modelo = Conversacion

    def listar_por_usuario(
        self, id_usuario: uuid.UUID, desplazamiento: int, limite: int
    ) -> list[Conversacion]:
        consulta = (
            select(Conversacion)
            .where(Conversacion.id_usuario == id_usuario)
            .order_by(Conversacion.fecha_ultimo_mensaje.desc())
            .offset(desplazamiento)
            .limit(limite)
        )
        return list(self._session.scalars(consulta))

    def contar_por_usuario(self, id_usuario: uuid.UUID) -> int:
        consulta = select(func.count()).where(Conversacion.id_usuario == id_usuario)
        return int(self._session.scalar(consulta) or 0)

    def listar_abiertas(self, id_usuario: uuid.UUID) -> list[Conversacion]:
        consulta = select(Conversacion).where(
            Conversacion.id_usuario == id_usuario,
            Conversacion.estado == EstadoConversacion.ABIERTA,
        )
        return list(self._session.scalars(consulta))

    def obtener_abierta_inactiva(
        self, id_usuario: uuid.UUID, antes_de: datetime
    ) -> Conversacion | None:
        consulta = (
            select(Conversacion)
            .where(
                Conversacion.id_usuario == id_usuario,
                Conversacion.estado == EstadoConversacion.ABIERTA,
                Conversacion.fecha_ultimo_mensaje < antes_de,
            )
            .order_by(Conversacion.fecha_ultimo_mensaje)
            .limit(1)
        )
        return self._session.scalar(consulta)

    def listar_todas_por_usuario(self, id_usuario: uuid.UUID) -> list[Conversacion]:
        consulta = select(Conversacion).where(Conversacion.id_usuario == id_usuario)
        return list(self._session.scalars(consulta))

    def listar_anteriores_a(self, instante: datetime) -> list[Conversacion]:
        consulta = select(Conversacion).where(Conversacion.fecha_ultimo_mensaje < instante)
        return list(self._session.scalars(consulta))


class MensajeRepository(RepositorioBase[Mensaje]):
    modelo = Mensaje

    def listar_ultimos(self, id_conversacion: uuid.UUID, limite: int) -> list[Mensaje]:
        consulta = (
            select(Mensaje)
            .where(Mensaje.id_conversacion == id_conversacion)
            .order_by(Mensaje.orden.desc())
            .limit(limite)
        )
        return list(reversed(list(self._session.scalars(consulta))))

    def listar_por_conversacion(self, id_conversacion: uuid.UUID) -> list[Mensaje]:
        consulta = (
            select(Mensaje)
            .where(Mensaje.id_conversacion == id_conversacion)
            .order_by(Mensaje.orden)
        )
        return list(self._session.scalars(consulta))

    def siguiente_orden(self, id_conversacion: uuid.UUID) -> int:
        consulta = select(func.coalesce(func.max(Mensaje.orden), 0)).where(
            Mensaje.id_conversacion == id_conversacion
        )
        return int(self._session.scalar(consulta) or 0) + 1

    def obtener_con_conversacion(self, id_mensaje: uuid.UUID) -> Mensaje | None:
        return self._session.get(Mensaje, id_mensaje)

    def contar_tutor(self, id_conversacion: uuid.UUID) -> int:
        consulta = select(func.count()).where(
            Mensaje.id_conversacion == id_conversacion, Mensaje.rol == RolMensaje.TUTOR
        )
        return int(self._session.scalar(consulta) or 0)


class EventoAprendizajeRepository(RepositorioBase[EventoAprendizaje]):
    modelo = EventoAprendizaje

    def contar_por_tipo(self, id_usuario: uuid.UUID) -> dict[TipoEvento, int]:
        consulta = (
            select(EventoAprendizaje.tipo, func.count())
            .where(EventoAprendizaje.id_usuario == id_usuario)
            .group_by(EventoAprendizaje.tipo)
        )
        return {tipo: int(total) for tipo, total in self._session.execute(consulta).all()}

    def contar_por_tipo_en_conversacion(self, id_conversacion: uuid.UUID) -> dict[TipoEvento, int]:
        consulta = (
            select(EventoAprendizaje.tipo, func.count())
            .where(EventoAprendizaje.id_conversacion == id_conversacion)
            .group_by(EventoAprendizaje.tipo)
        )
        return {tipo: int(total) for tipo, total in self._session.execute(consulta).all()}

    def listar_por_conversacion(self, id_conversacion: uuid.UUID) -> list[EventoAprendizaje]:
        consulta = select(EventoAprendizaje).where(
            EventoAprendizaje.id_conversacion == id_conversacion
        )
        return list(self._session.scalars(consulta))

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[EventoAprendizaje]:
        consulta = select(EventoAprendizaje).where(EventoAprendizaje.id_usuario == id_usuario)
        return list(self._session.scalars(consulta))


class PerfilAprendizajeRepository(RepositorioBase[PerfilAprendizaje]):
    modelo = PerfilAprendizaje

    def obtener_por_usuario(self, id_usuario: uuid.UUID) -> PerfilAprendizaje | None:
        consulta = select(PerfilAprendizaje).where(PerfilAprendizaje.id_usuario == id_usuario)
        return self._session.scalar(consulta)
