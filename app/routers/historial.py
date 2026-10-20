import uuid

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_historial_service, get_usuario_activo_id
from app.schemas.historial import HistorialPagina
from app.services.historial_service import HistorialService

TAMANO_MAXIMO = 50
router = APIRouter(prefix="/historial", tags=["historial"])


@router.get("/{uid}", response_model=HistorialPagina)
def listar(
    uid: uuid.UUID,
    pagina: int = Query(1, ge=1),
    tamano: int = Query(10, ge=1, le=TAMANO_MAXIMO),
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: HistorialService = Depends(get_historial_service),
) -> HistorialPagina:
    return servicio.listar(uid, id_usuario, pagina, tamano)
