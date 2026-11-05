from datetime import datetime

from sqlalchemy import or_, select

from app.models.autorizacion_acudiente import AutorizacionAcudiente
from app.models.enums import EstadoAutorizacion
from app.repositories.base import RepositorioBase


class AutorizacionRepository(RepositorioBase[AutorizacionAcudiente]):
    modelo = AutorizacionAcudiente

    def obtener_por_token_hash(self, token_hash: str) -> AutorizacionAcudiente | None:
        consulta = select(AutorizacionAcudiente).where(
            AutorizacionAcudiente.token_hash == token_hash
        )
        return self._session.scalar(consulta)

    def obtener_vigente_por_estudiante(
        self, correo_estudiante_hash: str, autorizada_desde: datetime
    ) -> AutorizacionAcudiente | None:
        consulta = (
            select(AutorizacionAcudiente)
            .where(
                AutorizacionAcudiente.correo_estudiante_hash == correo_estudiante_hash,
                AutorizacionAcudiente.estado == EstadoAutorizacion.AUTORIZADA,
                AutorizacionAcudiente.fecha_verificacion >= autorizada_desde,
            )
            .order_by(AutorizacionAcudiente.fecha_verificacion.desc())
            .limit(1)
        )
        return self._session.scalar(consulta)

    def fechas_solicitud_desde(self, correo_hash: str, desde: datetime) -> list[datetime]:
        """Fechas de las solicitudes recientes en las que el correo es acudiente o estudiante."""
        consulta = select(AutorizacionAcudiente.fecha_solicitud).where(
            or_(
                AutorizacionAcudiente.correo_acudiente_hash == correo_hash,
                AutorizacionAcudiente.correo_estudiante_hash == correo_hash,
            ),
            AutorizacionAcudiente.fecha_solicitud >= desde,
        )
        return list(self._session.scalars(consulta))

    def obtener_ultima_por_estudiante(
        self, correo_estudiante_hash: str
    ) -> AutorizacionAcudiente | None:
        consulta = (
            select(AutorizacionAcudiente)
            .where(AutorizacionAcudiente.correo_estudiante_hash == correo_estudiante_hash)
            .order_by(AutorizacionAcudiente.fecha_solicitud.desc())
            .limit(1)
        )
        return self._session.scalar(consulta)

    def obtener_rechazo_desde(
        self, correo_estudiante_hash: str, correo_acudiente_hash: str, desde: datetime
    ) -> AutorizacionAcudiente | None:
        """Rechazo reciente del mismo acudiente para el mismo estudiante (fecha_verificacion es
        la fecha en que el acudiente respondió)."""
        consulta = (
            select(AutorizacionAcudiente)
            .where(
                AutorizacionAcudiente.correo_estudiante_hash == correo_estudiante_hash,
                AutorizacionAcudiente.correo_acudiente_hash == correo_acudiente_hash,
                AutorizacionAcudiente.estado == EstadoAutorizacion.RECHAZADA,
                AutorizacionAcudiente.fecha_verificacion >= desde,
            )
            .order_by(AutorizacionAcudiente.fecha_verificacion.desc())
            .limit(1)
        )
        return self._session.scalar(consulta)

    def listar_pendientes_por_estudiante(
        self, correo_estudiante_hash: str
    ) -> list[AutorizacionAcudiente]:
        consulta = select(AutorizacionAcudiente).where(
            AutorizacionAcudiente.correo_estudiante_hash == correo_estudiante_hash,
            AutorizacionAcudiente.estado == EstadoAutorizacion.PENDIENTE_VERIFICACION,
        )
        return list(self._session.scalars(consulta))

    def listar_pendientes_vencidas(self, ahora: datetime) -> list[AutorizacionAcudiente]:
        consulta = select(AutorizacionAcudiente).where(
            AutorizacionAcudiente.estado == EstadoAutorizacion.PENDIENTE_VERIFICACION,
            AutorizacionAcudiente.fecha_expiracion_token < ahora,
        )
        return list(self._session.scalars(consulta))

    def listar_por_estudiante(self, correo_estudiante_hash: str) -> list[AutorizacionAcudiente]:
        consulta = select(AutorizacionAcudiente).where(
            AutorizacionAcudiente.correo_estudiante_hash == correo_estudiante_hash
        )
        return list(self._session.scalars(consulta))
