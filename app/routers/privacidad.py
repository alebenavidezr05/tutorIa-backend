import uuid

from fastapi import APIRouter, Depends, Response, status

from app.core.dependencies import (
    get_consentimiento_service,
    get_contexto,
    get_politica_service,
    get_privacidad_service,
    get_usuario_activo_id,
    get_usuario_actual_id,
)
from app.core.respuestas import respuesta_descarga
from app.schemas.auth import ContextoSolicitud
from app.schemas.privacidad import (
    AceptarPoliticaEntrada,
    CambioConsentimientoEntrada,
    ConsentimientoPublico,
    CumplimientoPublico,
    MisDatos,
    PoliticaPublica,
    SolicitudEntrada,
    SolicitudPublica,
)
from app.services.consentimiento_service import ConsentimientoService
from app.services.politica_service import PoliticaService
from app.services.privacidad_service import PrivacidadService

publico = APIRouter(tags=["privacidad"])
sesion = APIRouter(prefix="/privacidad", tags=["privacidad"])
router = APIRouter(prefix="/privacidad", tags=["privacidad"])


@publico.get("/politica-tratamiento", response_model=PoliticaPublica)
def politica(servicio: PoliticaService = Depends(get_politica_service)) -> PoliticaPublica:
    return servicio.obtener()


@publico.get("/cumplimiento", response_model=CumplimientoPublico)
def cumplimiento(servicio: PoliticaService = Depends(get_politica_service)) -> CumplimientoPublico:
    return servicio.cumplimiento()


@sesion.post("/aceptar-politica", response_model=list[ConsentimientoPublico])
def aceptar_politica(
    entrada: AceptarPoliticaEntrada,
    contexto: ContextoSolicitud = Depends(get_contexto),
    id_usuario: uuid.UUID = Depends(get_usuario_actual_id),
    servicio: ConsentimientoService = Depends(get_consentimiento_service),
) -> list[ConsentimientoPublico]:
    return servicio.aceptar_politica(id_usuario, entrada, contexto)


@router.get("/consentimientos", response_model=list[ConsentimientoPublico])
def consentimientos(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ConsentimientoService = Depends(get_consentimiento_service),
) -> list[ConsentimientoPublico]:
    return servicio.estado_actual(id_usuario)


@router.post("/consentimientos", response_model=list[ConsentimientoPublico])
def cambiar_consentimiento(
    entrada: CambioConsentimientoEntrada,
    contexto: ContextoSolicitud = Depends(get_contexto),
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ConsentimientoService = Depends(get_consentimiento_service),
) -> list[ConsentimientoPublico]:
    return servicio.cambiar(id_usuario, entrada, contexto)


@router.get("/mis-datos", response_model=MisDatos)
def mis_datos(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PrivacidadService = Depends(get_privacidad_service),
) -> MisDatos:
    return servicio.mis_datos(id_usuario)


@router.get("/mis-datos/exportar", response_class=Response)
def exportar(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PrivacidadService = Depends(get_privacidad_service),
) -> Response:
    return respuesta_descarga(servicio.exportar(id_usuario))


@router.post("/solicitudes", response_model=SolicitudPublica, status_code=status.HTTP_201_CREATED)
def crear_solicitud(
    entrada: SolicitudEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PrivacidadService = Depends(get_privacidad_service),
) -> SolicitudPublica:
    return servicio.crear_solicitud(id_usuario, entrada)


@router.get("/solicitudes", response_model=list[SolicitudPublica])
def listar_solicitudes(
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: PrivacidadService = Depends(get_privacidad_service),
) -> list[SolicitudPublica]:
    return servicio.listar_solicitudes(id_usuario)
