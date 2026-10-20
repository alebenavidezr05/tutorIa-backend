import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_plan_service, get_usuario_activo_id
from app.schemas.plan import GenerarPlanEntrada, PlanDetalle
from app.services.plan_service import PlanService

router = APIRouter(prefix="/plan-aprendizaje", tags=["plan"])


@router.post("", response_model=PlanDetalle, status_code=status.HTTP_201_CREATED)
def generar(
    entrada: GenerarPlanEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PlanService = Depends(get_plan_service),
) -> PlanDetalle:
    return servicio.generar(id_usuario, entrada)


@router.get("/{id_plan}", response_model=PlanDetalle)
def obtener(
    id_plan: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PlanService = Depends(get_plan_service),
) -> PlanDetalle:
    return servicio.obtener(id_usuario, id_plan)
