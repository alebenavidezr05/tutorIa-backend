import uuid

from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import DatoInvalidoError, RecursoNoEncontradoError
from app.models.enums import FormatoExplicacion, RolMensaje, TipoEvento
from app.models.evento_aprendizaje import EventoAprendizaje
from app.models.mensaje import Mensaje
from app.repositories.conversacion import (
    EventoAprendizajeRepository,
    MensajeRepository,
    PerfilAprendizajeRepository,
)
from app.schemas.conversacion import FeedbackEntrada
from app.services.aprendizaje.perfil_aprendizaje_service import PerfilAprendizajeService
from app.validators.propiedad import validar_recurso_propio


class FeedbackService:
    def __init__(
        self,
        mensajes: MensajeRepository,
        eventos: EventoAprendizajeRepository,
        perfiles_repo: PerfilAprendizajeRepository,
        perfiles: PerfilAprendizajeService,
        uow: UnitOfWork,
    ) -> None:
        self._mensajes = mensajes
        self._eventos = eventos
        self._perfiles_repo = perfiles_repo
        self._perfiles = perfiles
        self._uow = uow

    def registrar(
        self, id_usuario: uuid.UUID, id_mensaje: uuid.UUID, entrada: FeedbackEntrada
    ) -> None:
        mensaje = self._mensaje_del_tutor(id_usuario, id_mensaje)
        mensaje.util = entrada.util
        mensaje.motivo_feedback = entrada.motivo
        perfil = self._perfiles_repo.obtener_por_usuario(id_usuario)
        if perfil is not None and perfil.personalizacion_activa:
            self._eventos.agregar(
                EventoAprendizaje(
                    id_usuario=id_usuario,
                    id_conversacion=mensaje.id_conversacion,
                    id_mensaje=mensaje.id_mensaje,
                    tipo=TipoEvento.FEEDBACK_UTIL if entrada.util else TipoEvento.FEEDBACK_NO_UTIL,
                    valor=1.0 if entrada.util else 0.0,
                    fecha=ahora_utc(),
                )
            )
            formatos = [FormatoExplicacion(f) for f in (mensaje.formatos_usados or [])]
            self._perfiles.registrar_feedback(perfil, entrada.util, formatos)
        self._uow.commit()

    def _mensaje_del_tutor(self, id_usuario: uuid.UUID, id_mensaje: uuid.UUID) -> Mensaje:
        mensaje = self._mensajes.obtener_con_conversacion(id_mensaje)
        if mensaje is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(mensaje.conversacion.id_usuario, id_usuario)
        if mensaje.rol != RolMensaje.TUTOR:
            raise DatoInvalidoError("Solo puedes calificar respuestas del tutor.")
        return mensaje
