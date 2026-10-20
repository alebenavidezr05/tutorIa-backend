import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    get_alerta_service,
    get_feedback_service,
    get_trabajo_visual_service,
    get_usuario_activo_id,
)
from app.schemas.conversacion import FeedbackEntrada, ReporteEntrada
from app.schemas.visual import VisualPublico
from app.services.seguridad.alerta_seguridad_service import AlertaSeguridadService
from app.services.tutor.feedback_service import FeedbackService
from app.services.visual.trabajo_visual_service import TrabajoVisualService

router = APIRouter(prefix="/mensajes", tags=["mensajes"])


@router.post("/{id_mensaje}/feedback", status_code=status.HTTP_204_NO_CONTENT)
def feedback(
    id_mensaje: uuid.UUID,
    entrada: FeedbackEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: FeedbackService = Depends(get_feedback_service),
) -> None:
    servicio.registrar(id_usuario, id_mensaje, entrada)


@router.post("/{id_mensaje}/reportar", status_code=status.HTTP_204_NO_CONTENT)
def reportar(
    id_mensaje: uuid.UUID,
    entrada: ReporteEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: AlertaSeguridadService = Depends(get_alerta_service),
) -> None:
    servicio.reportar(id_usuario, id_mensaje, entrada)


@router.get("/{id_mensaje}/visual", response_model=VisualPublico)
def visual(
    id_mensaje: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: TrabajoVisualService = Depends(get_trabajo_visual_service),
) -> VisualPublico:
    return servicio.consultar(id_usuario, id_mensaje)
