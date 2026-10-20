import uuid

from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import RecursoNoEncontradoError
from app.models.alerta_seguridad import AlertaSeguridad
from app.models.enums import CategoriaAlerta, OrigenAlerta
from app.repositories.conversacion import ConversacionRepository, MensajeRepository
from app.repositories.seguridad import AlertaSeguridadRepository
from app.schemas.conversacion import ReporteEntrada
from app.validators.privacidad import redactar_datos_personales
from app.validators.propiedad import validar_recurso_propio
from app.validators.texto import normalizar_texto, truncar

MAX_DETALLE = 500


class AlertaSeguridadService:
    """Alertas para revisión humana: automáticas (moderación o ámbito) y reportes de usuarios."""

    def __init__(
        self,
        alertas: AlertaSeguridadRepository,
        mensajes: MensajeRepository,
        conversaciones: ConversacionRepository,
        uow: UnitOfWork,
    ) -> None:
        self._alertas = alertas
        self._mensajes = mensajes
        self._conversaciones = conversaciones
        self._uow = uow

    def registrar_automatica(
        self,
        id_usuario: uuid.UUID,
        id_mensaje: uuid.UUID | None,
        categoria: CategoriaAlerta,
        detalle: str | None,
    ) -> None:
        """No confirma: forma parte de la transacción del turno del tutor."""
        self._agregar(id_usuario, id_mensaje, OrigenAlerta.AUTOMATICA, categoria, detalle)

    def reportar(
        self, id_usuario: uuid.UUID, id_mensaje: uuid.UUID, entrada: ReporteEntrada
    ) -> None:
        mensaje = self._mensajes.obtener_con_conversacion(id_mensaje)
        if mensaje is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(mensaje.conversacion.id_usuario, id_usuario)
        self._agregar(
            id_usuario, id_mensaje, OrigenAlerta.USUARIO, entrada.categoria, entrada.comentario
        )
        self._uow.commit()

    def _agregar(
        self,
        id_usuario: uuid.UUID,
        id_mensaje: uuid.UUID | None,
        origen: OrigenAlerta,
        categoria: CategoriaAlerta,
        detalle: str | None,
    ) -> None:
        limpio = (
            truncar(redactar_datos_personales(normalizar_texto(detalle)), MAX_DETALLE)
            if detalle
            else None
        )
        self._alertas.agregar(
            AlertaSeguridad(
                id_usuario=id_usuario,
                id_mensaje=id_mensaje,
                origen=origen,
                categoria=categoria,
                detalle=limpio,
                fecha=ahora_utc(),
            )
        )
