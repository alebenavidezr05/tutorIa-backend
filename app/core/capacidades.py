"""Único lugar que define qué incluye cada plan: capacidades exclusivas y cupos diarios."""

from datetime import datetime

from app.core.config import Settings
from app.models.enums import CampoUso, Capacidad, EstadoSuscripcion, PlanSuscripcion
from app.models.suscripcion import Suscripcion

CAPACIDADES_POR_PLAN: dict[PlanSuscripcion, frozenset[Capacidad]] = {
    PlanSuscripcion.GRATUITO: frozenset(),
    PlanSuscripcion.PREMIUM: frozenset(Capacidad),
}
SUFIJO_LIMITE = {PlanSuscripcion.GRATUITO: "gratis", PlanSuscripcion.PREMIUM: "premium"}


def calcular_plan_efectivo(suscripcion: Suscripcion | None, ahora: datetime) -> PlanSuscripcion:
    """PREMIUM solo si está activa y no ha vencido; en cualquier otro caso rige el plan gratuito."""
    if suscripcion is None or suscripcion.plan != PlanSuscripcion.PREMIUM:
        return PlanSuscripcion.GRATUITO
    vigente = suscripcion.fecha_fin is None or suscripcion.fecha_fin > ahora
    if suscripcion.estado == EstadoSuscripcion.ACTIVA and vigente:
        return PlanSuscripcion.PREMIUM
    return PlanSuscripcion.GRATUITO


def capacidades_de(plan: PlanSuscripcion) -> frozenset[Capacidad]:
    return CAPACIDADES_POR_PLAN[plan]


def limite_de(plan: PlanSuscripcion, campo: CampoUso, settings: Settings) -> int:
    valor: int = getattr(settings, f"limite_{campo.value}_{SUFIJO_LIMITE[plan]}")
    return valor
