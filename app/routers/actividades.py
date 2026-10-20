import uuid

from fastapi import APIRouter, Depends

from app.core.dependencies import get_actividad_service, get_usuario_activo_id
from app.schemas.actividad import ActividadPublica, ActualizarActividadEntrada
from app.services.actividad_service import ActividadService

router = APIRouter(prefix="/actividades", tags=["actividades"])


@router.patch("/{id_actividad}", response_model=ActividadPublica)
def actualizar(
    id_actividad: uuid.UUID,
    entrada: ActualizarActividadEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ActividadService = Depends(get_actividad_service),
) -> ActividadPublica:
    return servicio.actualizar(id_usuario, id_actividad, entrada)
