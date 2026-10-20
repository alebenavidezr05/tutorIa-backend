import uuid
from collections.abc import Set

from app.schemas.bloques import PlanGenerado
from app.validators.entrega_directa import contiene_entrega_directa
from app.validators.resultado import ResultadoValidacion

MIN_TECNICAS = 2
MIN_ACTIVIDADES = 3
MAX_ACTIVIDADES = 6


class PlanValidator:
    """Capa 3 del plan: estructura, ausencia de entrega directa y citas válidas."""

    def validar(self, plan: PlanGenerado, ids_fuentes: Set[uuid.UUID]) -> ResultadoValidacion:
        motivos = [*self._motivos_estructura(plan), *self._motivos_contenido(plan)]
        if not set(plan.fuentes_usadas) <= ids_fuentes:
            motivos.append("cita fuentes que no se entregaron")
        return ResultadoValidacion.desde_motivos(motivos)

    def _motivos_estructura(self, plan: PlanGenerado) -> list[str]:
        motivos = []
        if not plan.titulo.strip():
            motivos.append("falta el título")
        if len([t for t in plan.tecnicas_estudio if t.strip()]) < MIN_TECNICAS:
            motivos.append(f"se requieren al menos {MIN_TECNICAS} técnicas de estudio")
        actividades = [a for a in plan.actividades if a.strip()]
        if not MIN_ACTIVIDADES <= len(actividades) <= MAX_ACTIVIDADES:
            motivos.append(f"se requieren entre {MIN_ACTIVIDADES} y {MAX_ACTIVIDADES} actividades")
        return motivos

    def _motivos_contenido(self, plan: PlanGenerado) -> list[str]:
        textos = [plan.explicacion, *plan.tecnicas_estudio, *plan.actividades]
        if any(contiene_entrega_directa(t) for t in textos):
            return ["entrega respuestas directas"]
        return []
