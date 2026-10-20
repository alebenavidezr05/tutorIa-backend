import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    get_consolidacion_service,
    get_conversacion_service,
    get_referencias_service,
    get_tareas,
    get_tutor_service,
    get_usuario_activo_id,
)
from app.core.tareas import TareasSegundoPlano
from app.schemas.conversacion import (
    ConversacionDetalle,
    ConversacionesPagina,
    ConversacionPublica,
    EnviarMensajeEntrada,
    IniciarConversacionEntrada,
    MensajeTutorPublico,
    ResumenSesion,
)
from app.schemas.fuente import ReferenciaPublica
from app.services.fuentes.referencias_service import ReferenciasService
from app.services.tutor.consolidacion_service import ConsolidacionService
from app.services.tutor.conversacion_service import ConversacionService
from app.services.tutor.tutor_service import TutorService

TAMANO_MAXIMO = 50
router = APIRouter(prefix="/conversaciones", tags=["conversaciones"])


@router.post("", response_model=ConversacionPublica, status_code=status.HTTP_201_CREATED)
def iniciar(
    entrada: IniciarConversacionEntrada,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ConversacionService = Depends(get_conversacion_service),
) -> ConversacionPublica:
    return servicio.iniciar(id_usuario, entrada)


@router.get("", response_model=ConversacionesPagina)
def listar(
    pagina: int = Query(1, ge=1),
    tamano: int = Query(10, ge=1, le=TAMANO_MAXIMO),
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ConversacionService = Depends(get_conversacion_service),
) -> ConversacionesPagina:
    return servicio.listar(id_usuario, pagina, tamano)


@router.get("/{id_conversacion}", response_model=ConversacionDetalle)
def obtener(
    id_conversacion: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ConversacionService = Depends(get_conversacion_service),
) -> ConversacionDetalle:
    return servicio.obtener(id_usuario, id_conversacion)


@router.post(
    "/{id_conversacion}/mensajes",
    response_model=MensajeTutorPublico,
    status_code=status.HTTP_201_CREATED,
)
def enviar_mensaje(
    id_conversacion: uuid.UUID,
    entrada: EnviarMensajeEntrada,
    tareas: TareasSegundoPlano = Depends(get_tareas),
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: TutorService = Depends(get_tutor_service),
) -> MensajeTutorPublico:
    return servicio.responder(id_usuario, id_conversacion, entrada, tareas)


@router.post("/{id_conversacion}/cerrar", response_model=ResumenSesion)
def cerrar(
    id_conversacion: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ConsolidacionService = Depends(get_consolidacion_service),
) -> ResumenSesion:
    return servicio.cerrar(id_usuario, id_conversacion)


@router.get("/{id_conversacion}/referencias", response_model=list[ReferenciaPublica])
def referencias(
    id_conversacion: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ReferenciasService = Depends(get_referencias_service),
) -> list[ReferenciaPublica]:
    return servicio.de_conversacion(id_usuario, id_conversacion)


@router.delete("/{id_conversacion}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    id_conversacion: uuid.UUID,
    id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
    servicio: ConversacionService = Depends(get_conversacion_service),
) -> None:
    servicio.eliminar(id_usuario, id_conversacion)
