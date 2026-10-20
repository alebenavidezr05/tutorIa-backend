import uuid
from collections.abc import Mapping
from datetime import timedelta

from app.core.config import Settings
from app.core.tiempo import ahora_utc, hoy_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import (
    CompraNoPermitidaError,
    OperacionNoPermitidaError,
    RecursoNoEncontradoError,
)
from app.models.enums import EstadoSuscripcion, PlanSuscripcion
from app.models.evento_pago import EventoPago
from app.models.suscripcion import Suscripcion
from app.pagos.base import (
    TIPO_PAGO_APROBADO,
    TIPO_SUSCRIPCION_CANCELADA,
    EventoPasarela,
    PasarelaPagos,
)
from app.repositories.suscripcion import EventoPagoRepository, SuscripcionRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.suscripcion import CheckoutPublico
from app.services.autorizacion_service import AutorizacionService
from app.services.suscripcion_service import SuscripcionService
from app.validators.edad import es_menor

DIAS_PLAN_ANUAL = 365
DESCRIPCION_PREMIUM = "TutorIA Premium (anual)"
MONEDA = "COP"


class PagoService:
    """Checkout y webhooks. Nunca se reciben ni guardan datos de tarjeta."""

    def __init__(
        self,
        suscripciones_repo: SuscripcionRepository,
        eventos: EventoPagoRepository,
        usuarios: UsuarioRepository,
        suscripciones: SuscripcionService,
        autorizaciones: AutorizacionService,
        pasarela: PasarelaPagos,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._suscripciones_repo = suscripciones_repo
        self._eventos = eventos
        self._usuarios = usuarios
        self._suscripciones = suscripciones
        self._autorizaciones = autorizaciones
        self._pasarela = pasarela
        self._settings = settings
        self._uow = uow

    def iniciar_checkout(self, id_usuario: uuid.UUID) -> CheckoutPublico:
        if self._suscripciones.plan_efectivo(id_usuario) == PlanSuscripcion.PREMIUM:
            raise OperacionNoPermitidaError("Ya tienes el plan Premium activo.")
        self._asegurar_puede_comprar(id_usuario)
        suscripcion = self._suscripcion(id_usuario)
        suscripcion.referencia_pasarela = uuid.uuid4().hex
        self._uow.commit()
        url = self._pasarela.crear_checkout(
            suscripcion.referencia_pasarela,
            self._settings.premium_precio_anual_cop,
            DESCRIPCION_PREMIUM,
        )
        return CheckoutPublico(url_pago=url)

    def procesar_webhook(self, proveedor: str, cuerpo: bytes, cabeceras: Mapping[str, str]) -> None:
        if proveedor != self._pasarela.nombre:
            raise RecursoNoEncontradoError()
        evento = self._pasarela.verificar_webhook(cuerpo, cabeceras)
        if self._eventos.existe(proveedor, evento.id_evento):
            return
        self._eventos.agregar(
            EventoPago(
                proveedor=proveedor,
                id_evento_externo=evento.id_evento,
                tipo=evento.tipo,
                fecha=ahora_utc(),
            )
        )
        self._aplicar(evento)
        self._uow.commit()

    def _asegurar_puede_comprar(self, id_usuario: uuid.UUID) -> None:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        menor = es_menor(usuario.fecha_nacimiento, hoy_utc(), self._settings.edad_mayoria)
        if menor and not self._autorizaciones.permite_compras(usuario.correo_hash):
            raise CompraNoPermitidaError()

    def _suscripcion(self, id_usuario: uuid.UUID) -> Suscripcion:
        suscripcion = self._suscripciones_repo.obtener_vigente_por_usuario(id_usuario)
        if suscripcion is None:
            raise RecursoNoEncontradoError()
        return suscripcion

    def _aplicar(self, evento: EventoPasarela) -> None:
        suscripcion = self._suscripciones_repo.obtener_por_referencia(evento.referencia)
        if suscripcion is None:
            return
        ahora = ahora_utc()
        if evento.tipo == TIPO_PAGO_APROBADO:
            suscripcion.plan = PlanSuscripcion.PREMIUM
            suscripcion.estado = EstadoSuscripcion.ACTIVA
            suscripcion.fecha_inicio = ahora
            suscripcion.fecha_fin = ahora + timedelta(days=DIAS_PLAN_ANUAL)
        elif evento.tipo == TIPO_SUSCRIPCION_CANCELADA:
            suscripcion.estado = EstadoSuscripcion.CANCELADA
