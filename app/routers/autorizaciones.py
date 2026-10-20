from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_autorizacion_service, get_contexto
from app.schemas.auth import ContextoSolicitud
from app.schemas.autorizacion import (
    AutorizacionPublica,
    MensajeGenerico,
    RevocarAutorizacionEntrada,
    SolicitudAutorizacionEntrada,
    TokenAutorizacionEntrada,
)
from app.services.autorizacion_service import AutorizacionService

publico = APIRouter(prefix="/autorizaciones", tags=["autorizaciones"])


@publico.post("", response_model=MensajeGenerico, status_code=status.HTTP_202_ACCEPTED)
def solicitar(
    entrada: SolicitudAutorizacionEntrada,
    contexto: ContextoSolicitud = Depends(get_contexto),
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> MensajeGenerico:
    return servicio.solicitar(entrada, contexto)


@publico.post("/consultar", response_model=AutorizacionPublica)
def consultar(
    entrada: TokenAutorizacionEntrada,
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> AutorizacionPublica:
    return servicio.consultar(entrada)


@publico.post("/confirmar", response_model=AutorizacionPublica)
def confirmar(
    entrada: TokenAutorizacionEntrada,
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> AutorizacionPublica:
    return servicio.confirmar(entrada)


@publico.post("/revocar", response_model=AutorizacionPublica)
def revocar(
    entrada: RevocarAutorizacionEntrada,
    contexto: ContextoSolicitud = Depends(get_contexto),
    servicio: AutorizacionService = Depends(get_autorizacion_service),
) -> AutorizacionPublica:
    return servicio.revocar(entrada, contexto)
