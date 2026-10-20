import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    get_diagnostico_service,
    get_evaluacion_service,
    get_usuario_activo_id,
)
from app.schemas.diagnostico import (
    CrearDiagnosticoEntrada,
    CuestionarioPublico,
    RespuestasEntrada,
    ResultadoDiagnostico,
)
from app.services.diagnostico_service import DiagnosticoService
from app.services.evaluacion_service import EvaluacionService

router = APIRouter(prefix="/diagnostico", tags=["diagnostico"])


@router.post("", response_model=CuestionarioPublico, status_code=status.HTTP_201_CREATED)
def crear(
    entrada: CrearDiagnosticoEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: DiagnosticoService = Depends(get_diagnostico_service),
) -> CuestionarioPublico:
    return servicio.crear_sesion(id_usuario, entrada)


@router.get("/{id_sesion}", response_model=CuestionarioPublico)
def obtener(
    id_sesion: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: DiagnosticoService = Depends(get_diagnostico_service),
) -> CuestionarioPublico:
    return servicio.obtener_cuestionario(id_usuario, id_sesion)


@router.post("/{id_sesion}/respuestas", response_model=ResultadoDiagnostico)
def responder(
    id_sesion: uuid.UUID,
    entrada: RespuestasEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: EvaluacionService = Depends(get_evaluacion_service),
) -> ResultadoDiagnostico:
    return servicio.evaluar(id_usuario, id_sesion, entrada)
