import uuid

from fastapi import APIRouter, Depends, Form, Response, status

from app.core.dependencies import get_archivo_service, get_entrada_archivo, get_usuario_activo_id
from app.core.respuestas import respuesta_descarga
from app.schemas.archivo import ArchivoPublico, ContextoArchivo, EntradaArchivo
from app.services.archivo_service import ArchivoService

router = APIRouter(prefix="/archivos", tags=["archivos"])


@router.post("", response_model=ArchivoPublico, status_code=status.HTTP_201_CREATED)
def subir(
    contexto: ContextoArchivo = Form(...),
    id_contexto: uuid.UUID = Form(...),
    entrada: EntradaArchivo = Depends(get_entrada_archivo),
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ArchivoService = Depends(get_archivo_service),
) -> ArchivoPublico:
    return servicio.subir(id_usuario, entrada, contexto, id_contexto)


@router.get("/{id_archivo}/contenido", response_class=Response)
def descargar(
    id_archivo: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ArchivoService = Depends(get_archivo_service),
) -> Response:
    return respuesta_descarga(servicio.descargar(id_usuario, id_archivo))


@router.delete("/{id_archivo}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    id_archivo: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ArchivoService = Depends(get_archivo_service),
) -> None:
    servicio.eliminar(id_usuario, id_archivo)
