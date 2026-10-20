import uuid
from datetime import date, datetime

from sqlalchemy import select

from app.models.alerta_seguridad import AlertaSeguridad
from app.models.consentimiento import Consentimiento
from app.models.enums import EstadoAlerta, EstadoSolicitud
from app.models.solicitud_titular import SolicitudTitular
from app.repositories.base import RepositorioBase


class AlertaSeguridadRepository(RepositorioBase[AlertaSeguridad]):
    modelo = AlertaSeguridad

    def listar_abiertas(self) -> list[AlertaSeguridad]:
        consulta = (
            select(AlertaSeguridad)
            .where(AlertaSeguridad.estado == EstadoAlerta.ABIERTA)
            .order_by(AlertaSeguridad.fecha)
        )
        return list(self._session.scalars(consulta))

    def listar_anteriores_a(self, instante: datetime) -> list[AlertaSeguridad]:
        consulta = select(AlertaSeguridad).where(AlertaSeguridad.fecha < instante)
        return list(self._session.scalars(consulta))

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[AlertaSeguridad]:
        consulta = select(AlertaSeguridad).where(AlertaSeguridad.id_usuario == id_usuario)
        return list(self._session.scalars(consulta))


class ConsentimientoRepository(RepositorioBase[Consentimiento]):
    """Solo inserta y consulta: la prueba de autorización nunca se modifica ni se borra."""

    modelo = Consentimiento

    def insertar(self, consentimiento: Consentimiento) -> Consentimiento:
        return self.agregar(consentimiento)

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[Consentimiento]:
        consulta = (
            select(Consentimiento)
            .where(Consentimiento.id_usuario == id_usuario)
            .order_by(Consentimiento.fecha)
        )
        return list(self._session.scalars(consulta))

    def listar_por_correo_hash(self, correo_hash: str) -> list[Consentimiento]:
        consulta = (
            select(Consentimiento)
            .where(Consentimiento.correo_hash == correo_hash)
            .order_by(Consentimiento.fecha)
        )
        return list(self._session.scalars(consulta))


class SolicitudTitularRepository(RepositorioBase[SolicitudTitular]):
    modelo = SolicitudTitular

    def crear(self, solicitud: SolicitudTitular) -> SolicitudTitular:
        return self.agregar(solicitud)

    def listar_por_usuario(self, id_usuario: uuid.UUID) -> list[SolicitudTitular]:
        consulta = (
            select(SolicitudTitular)
            .where(SolicitudTitular.id_usuario == id_usuario)
            .order_by(SolicitudTitular.fecha_recepcion.desc())
        )
        return list(self._session.scalars(consulta))

    def listar_por_vencer(self, limite: date) -> list[SolicitudTitular]:
        consulta = (
            select(SolicitudTitular)
            .where(
                SolicitudTitular.estado.in_([EstadoSolicitud.RECIBIDA, EstadoSolicitud.EN_TRAMITE]),
                SolicitudTitular.fecha_limite <= limite,
            )
            .order_by(SolicitudTitular.fecha_limite)
        )
        return list(self._session.scalars(consulta))
