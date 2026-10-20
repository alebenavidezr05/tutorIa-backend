import uuid

from fastapi import APIRouter, Depends, Response

from app.core.dependencies import get_recurso_visual_service, get_usuario_activo_id
from app.core.respuestas import respuesta_descarga
from app.services.visual.recurso_visual_service import RecursoVisualService

router = APIRouter(prefix="/recursos", tags=["recursos"])


@router.get("/{id_recurso}/imagen", response_class=Response)
def imagen(
    id_recurso: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: RecursoVisualService = Depends(get_recurso_visual_service),
) -> Response:
    return respuesta_descarga(servicio.obtener_imagen(id_usuario, id_recurso), adjunto=False)
