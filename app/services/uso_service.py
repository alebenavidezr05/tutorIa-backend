import uuid

from app.core.capacidades import calcular_plan_efectivo, limite_de
from app.core.config import Settings
from app.core.tiempo import ahora_utc, hoy_utc
from app.exceptions.base import AppError, LimiteFreemiumError, LimiteUsoError
from app.models.enums import CampoUso, PlanSuscripcion
from app.repositories.suscripcion import SuscripcionRepository
from app.repositories.uso import UsoDiarioRepository

# Mensajes y planes del plan gratuito invitan a Premium; el resto son topes de costo (429).
CAMPOS_FREEMIUM = {CampoUso.MENSAJES, CampoUso.PLANES}


class UsoService:
    """Cupos diarios por usuario. `consumir` es un UPDATE atómico dentro de la transacción del caso
    de uso; `asegurar_disponible` es una lectura previa para no gastar en IA sin cupo."""

    def __init__(
        self,
        usos: UsoDiarioRepository,
        suscripciones: SuscripcionRepository,
        settings: Settings,
    ) -> None:
        self._usos = usos
        self._suscripciones = suscripciones
        self._settings = settings

    def consumir(self, id_usuario: uuid.UUID, campo: CampoUso) -> None:
        if not self.intentar_consumir(id_usuario, campo):
            raise self._error_limite(id_usuario, campo)

    def intentar_consumir(self, id_usuario: uuid.UUID, campo: CampoUso) -> bool:
        limite = self._limite(id_usuario, campo)
        return self._usos.incrementar_si_hay_cupo(id_usuario, hoy_utc(), campo, limite)

    def asegurar_disponible(self, id_usuario: uuid.UUID, campo: CampoUso) -> None:
        if self.restante(id_usuario, campo) <= 0:
            raise self._error_limite(id_usuario, campo)

    def restante(self, id_usuario: uuid.UUID, campo: CampoUso) -> int:
        uso = self._usos.obtener(id_usuario, hoy_utc())
        usados = getattr(uso, campo.value) if uso else 0
        return max(self._limite(id_usuario, campo) - usados, 0)

    def restantes(self, id_usuario: uuid.UUID) -> dict[CampoUso, int]:
        return {campo: self.restante(id_usuario, campo) for campo in CampoUso}

    def _plan(self, id_usuario: uuid.UUID) -> PlanSuscripcion:
        return calcular_plan_efectivo(
            self._suscripciones.obtener_vigente_por_usuario(id_usuario), ahora_utc()
        )

    def _limite(self, id_usuario: uuid.UUID, campo: CampoUso) -> int:
        return limite_de(self._plan(id_usuario), campo, self._settings)

    def _error_limite(self, id_usuario: uuid.UUID, campo: CampoUso) -> AppError:
        gratuito = self._plan(id_usuario) == PlanSuscripcion.GRATUITO
        if campo in CAMPOS_FREEMIUM and gratuito:
            return LimiteFreemiumError(detalles={"campo": campo.value})
        return LimiteUsoError(detalles={"campo": campo.value})
