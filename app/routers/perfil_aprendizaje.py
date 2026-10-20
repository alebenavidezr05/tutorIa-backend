import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import (
    get_contexto,
    get_perfil_aprendizaje_service,
    get_usuario_activo_id,
)
from app.schemas.auth import ContextoSolicitud
from app.schemas.perfil_aprendizaje import CambioPersonalizacion, PerfilAprendizajePublico
from app.services.aprendizaje.perfil_aprendizaje_service import PerfilAprendizajeService

router = APIRouter(prefix="/perfil-aprendizaje", tags=["perfil-aprendizaje"])


@router.get("", response_model=PerfilAprendizajePublico)
def obtener(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PerfilAprendizajeService = Depends(get_perfil_aprendizaje_service),
) -> PerfilAprendizajePublico:
    return servicio.obtener(id_usuario)


@router.put("/personalizacion", response_model=PerfilAprendizajePublico)
def cambiar_personalizacion(
    entrada: CambioPersonalizacion,
    contexto: ContextoSolicitud = Depends(get_contexto),
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PerfilAprendizajeService = Depends(get_perfil_aprendizaje_service),
) -> PerfilAprendizajePublico:
    return servicio.activar_personalizacion(id_usuario, entrada.activa, contexto)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def reiniciar(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PerfilAprendizajeService = Depends(get_perfil_aprendizaje_service),
) -> None:
    servicio.reiniciar(id_usuario)
