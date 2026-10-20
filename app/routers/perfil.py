import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_perfil_service, get_usuario_activo_id
from app.schemas.usuario import ActualizarPerfilEntrada, UsuarioPublico
from app.services.perfil_service import PerfilService

router = APIRouter(prefix="/perfil", tags=["perfil"])


@router.get("/{uid}", response_model=UsuarioPublico)
def obtener(
    uid: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PerfilService = Depends(get_perfil_service),
) -> UsuarioPublico:
    return servicio.obtener(uid, id_usuario)


@router.put("/{uid}", response_model=UsuarioPublico)
def actualizar(
    uid: uuid.UUID,
    entrada: ActualizarPerfilEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PerfilService = Depends(get_perfil_service),
) -> UsuarioPublico:
    return servicio.actualizar(uid, id_usuario, entrada)


@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def desactivar(
    uid: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PerfilService = Depends(get_perfil_service),
) -> None:
    servicio.desactivar(uid, id_usuario)
