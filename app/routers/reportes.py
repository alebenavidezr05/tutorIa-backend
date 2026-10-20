import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.core.dependencies import (
    get_reporte_service,
    get_usuario_activo_id,
    requiere_reporte_progreso,
)
from app.core.respuestas import respuesta_descarga
from app.services.reporte_progreso_service import ReporteProgresoService

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get(
    "/progreso",
    response_class=Response,
    dependencies=[Depends(requiere_reporte_progreso)],
)
def progreso(
    formato: Literal["csv"] = Query("csv"),
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ReporteProgresoService = Depends(get_reporte_service),
) -> Response:
    return respuesta_descarga(servicio.generar_csv(id_usuario))
