import uuid

from app.core.capacidades import calcular_plan_efectivo, capacidades_de
from app.core.tiempo import ahora_utc
from app.exceptions.base import FuncionPremiumError, RecursoNoEncontradoError
from app.models.enums import CampoUso, Capacidad, EstadoSuscripcion, PlanSuscripcion
from app.models.suscripcion import Suscripcion
from app.repositories.suscripcion import SuscripcionRepository
from app.schemas.suscripcion import LimitesPublicos, SuscripcionPublica
from app.services.uso_service import UsoService


class SuscripcionService:
    """Plan efectivo, capacidades y límites. El servidor decide siempre: el cliente solo muestra."""

    def __init__(self, suscripciones: SuscripcionRepository, uso: UsoService) -> None:
        self._suscripciones = suscripciones
        self._uso = uso

    def obtener_actual(self, id_usuario: uuid.UUID) -> SuscripcionPublica:
        suscripcion = self._vigente(id_usuario)
        plan = self.plan_efectivo(id_usuario)
        return SuscripcionPublica(
            plan=plan,
            estado=self._estado_visible(suscripcion, plan),
            fecha_inicio=suscripcion.fecha_inicio,
            fecha_fin=suscripcion.fecha_fin,
            capacidades=sorted(c.value for c in capacidades_de(plan)),
            limites=self._limites(id_usuario),
        )

    def plan_efectivo(self, id_usuario: uuid.UUID) -> PlanSuscripcion:
        return calcular_plan_efectivo(
            self._suscripciones.obtener_vigente_por_usuario(id_usuario), ahora_utc()
        )

    def tiene_capacidad(self, id_usuario: uuid.UUID, capacidad: Capacidad) -> bool:
        return capacidad in capacidades_de(self.plan_efectivo(id_usuario))

    def asegurar_capacidad(self, id_usuario: uuid.UUID, capacidad: Capacidad) -> None:
        if not self.tiene_capacidad(id_usuario, capacidad):
            raise FuncionPremiumError(detalles={"capacidad": capacidad.value})

    def _vigente(self, id_usuario: uuid.UUID) -> Suscripcion:
        suscripcion = self._suscripciones.obtener_vigente_por_usuario(id_usuario)
        if suscripcion is None:
            raise RecursoNoEncontradoError()
        return suscripcion

    @staticmethod
    def _estado_visible(suscripcion: Suscripcion, plan: PlanSuscripcion) -> EstadoSuscripcion:
        # Un Premium vencido se muestra como VENCIDA aunque la fila aún diga ACTIVA.
        if suscripcion.plan == PlanSuscripcion.PREMIUM and plan == PlanSuscripcion.GRATUITO:
            return (
                EstadoSuscripcion.VENCIDA
                if suscripcion.estado == EstadoSuscripcion.ACTIVA
                else suscripcion.estado
            )
        return suscripcion.estado

    def _limites(self, id_usuario: uuid.UUID) -> LimitesPublicos:
        restantes = self._uso.restantes(id_usuario)
        return LimitesPublicos(
            mensajes_restantes_hoy=restantes[CampoUso.MENSAJES],
            planes_restantes_hoy=restantes[CampoUso.PLANES],
            imagenes_ia_restantes_hoy=restantes[CampoUso.IMAGENES_IA],
            busquedas_video_restantes_hoy=restantes[CampoUso.BUSQUEDAS_VIDEO],
            archivos_restantes_hoy=restantes[CampoUso.ARCHIVOS],
        )
