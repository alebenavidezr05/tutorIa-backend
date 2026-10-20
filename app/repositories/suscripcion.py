import uuid

from sqlalchemy import select

from app.models.evento_pago import EventoPago
from app.models.suscripcion import Suscripcion
from app.repositories.base import RepositorioBase


class SuscripcionRepository(RepositorioBase[Suscripcion]):
    modelo = Suscripcion

    def obtener_vigente_por_usuario(self, id_usuario: uuid.UUID) -> Suscripcion | None:
        consulta = (
            select(Suscripcion)
            .where(Suscripcion.id_usuario == id_usuario)
            .order_by(Suscripcion.fecha_inicio.desc())
            .limit(1)
        )
        return self._session.scalar(consulta)

    def obtener_por_referencia(self, referencia: str) -> Suscripcion | None:
        consulta = select(Suscripcion).where(Suscripcion.referencia_pasarela == referencia)
        return self._session.scalar(consulta)


class EventoPagoRepository(RepositorioBase[EventoPago]):
    modelo = EventoPago

    def existe(self, proveedor: str, id_evento_externo: str) -> bool:
        consulta = select(EventoPago.id_evento_pago).where(
            EventoPago.proveedor == proveedor, EventoPago.id_evento_externo == id_evento_externo
        )
        return self._session.scalar(consulta) is not None
