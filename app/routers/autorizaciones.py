import uuid

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_autorizacion_service, get_contexto, get_usuario_actual_id
from app.schemas.auth import ContextoSolicitud
from app.schemas.autorizacion import (
    AutorizacionPublica,
    ConfirmarAutorizacionEntrada,
    MensajeGenerico,
    MiAutorizacion,
    ReenviarAutorizacionEntrada,
    RevocarAutorizacionEntrada,
    TokenAutorizacionEntrada,
)
from app.services.autorizacion_service import AutorizacionService

# El acudiente no tiene cuenta: estas rutas se autentican con el token del enlace.
publico = APIRouter(prefix="/autorizaciones", tags=["autorizaciones"])
# El estudiante pendiente: sesión válida aunque la cuenta no esté activa.
sesion = APIRouter(prefix="/autorizaciones", tags=["autorizaciones"])


@sesion.get("/mia", response_model=MiAutorizacion)
def mia(
    id_usuario: uuid.UUID = Depends(get_usuario_actual_id),
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> MiAutorizacion:
    return servicio.mia(id_usuario)


@sesion.post("/reenviar", response_model=MensajeGenerico, status_code=status.HTTP_202_ACCEPTED)
def reenviar(
    entrada: ReenviarAutorizacionEntrada,
    contexto: ContextoSolicitud = Depends(get_contexto),
    id_usuario: uuid.UUID = Depends(get_usuario_actual_id),
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> MensajeGenerico:
    return servicio.reenviar(id_usuario, entrada, contexto)


@publico.post("/consultar", response_model=AutorizacionPublica)
def consultar(
    entrada: TokenAutorizacionEntrada,
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> AutorizacionPublica:
    return servicio.consultar(entrada)


@publico.post("/confirmar", response_model=AutorizacionPublica)
def confirmar(
    entrada: ConfirmarAutorizacionEntrada,
    contexto: ContextoSolicitud = Depends(get_contexto),
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> AutorizacionPublica:
    return servicio.confirmar(entrada, contexto)


@publico.post("/rechazar", response_model=AutorizacionPublica)
def rechazar(
    entrada: TokenAutorizacionEntrada,
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> AutorizacionPublica:
    return servicio.rechazar(entrada)


@publico.post("/revocar", response_model=AutorizacionPublica)
def revocar(
    entrada: RevocarAutorizacionEntrada,
    contexto: ContextoSolicitud = Depends(get_contexto),
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> AutorizacionPublica:
    return servicio.revocar(entrada, contexto)
