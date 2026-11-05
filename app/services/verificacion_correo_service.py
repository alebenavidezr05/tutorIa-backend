import logging
import secrets
import uuid
from datetime import timedelta

from app.core.config import Settings
from app.core.tiempo import ahora_utc, segundos_hasta
from app.core.unit_of_work import UnitOfWork
from app.correo import plantillas
from app.correo.base import Correo, CorreoClient
from app.correo.tolerante import enviar_sin_fallar
from app.crypto.indice_ciego import sha256_hex
from app.exceptions.base import (
    CorreoYaVerificadoError,
    SolicitudesExcesivasError,
    TokenInvalidoError,
    VerificacionInvalidaError,
)
from app.models.usuario import Usuario
from app.models.verificacion_correo import VerificacionCorreo
from app.repositories.usuario import UsuarioRepository
from app.repositories.verificacion_correo import VerificacionCorreoRepository
from app.schemas.autorizacion import MensajeGenerico
from app.schemas.verificacion_correo import (
    EstadoVerificacionCorreo,
    VerificacionCorreoResultado,
    VerificarCorreoEntrada,
)
from app.validators.privacidad import enmascarar_correo

logger = logging.getLogger(__name__)

BYTES_TOKEN = 32
VENTANA_ENVIOS = timedelta(hours=1)
RUTA_VERIFICAR = "/verificar-correo#token={token}"
MENSAJE_REENVIO = "Te enviamos un nuevo enlace para confirmar tu correo."


class VerificacionCorreoService:
    """Confirma que el correo es de quien se registra. Mismo patrón que la autorización del
    acudiente: token de un solo uso en el fragmento del enlace, guardado solo como SHA-256."""

    def __init__(
        self,
        verificaciones: VerificacionCorreoRepository,
        usuarios: UsuarioRepository,
        correo: CorreoClient,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._verificaciones = verificaciones
        self._usuarios = usuarios
        self._correo = correo
        self._settings = settings
        self._uow = uow

    def crear_para_registro(self, usuario: Usuario) -> Correo | None:
        """Dentro de la transacción del registro (no confirma). Devuelve el correo para enviarlo
        tras el commit, o None si esa dirección superó el tope por hora."""
        excedido = self._espera_por_frecuencia(usuario) > 0
        token = self._crear(usuario)
        if excedido:
            logger.warning("verificacion_correo_omitido motivo=frecuencia")
            return None
        return self._correo_verificacion(usuario, token)

    def enviar_sin_fallar(self, correo: Correo | None) -> None:
        if correo is not None:
            enviar_sin_fallar(self._correo, correo, "verificacion_correo_no_enviado")

    def verificar(self, entrada: VerificarCorreoEntrada) -> VerificacionCorreoResultado:
        verificacion = self._verificaciones.obtener_por_token_hash(sha256_hex(entrada.token))
        usuario = self._usuarios.obtener_por_id(verificacion.id_usuario) if verificacion else None
        if verificacion is None or usuario is None or not usuario.activo:
            raise VerificacionInvalidaError()
        # Idempotente: el mismo enlace, ya usado por una cuenta verificada, responde igual.
        if verificacion.usado and usuario.correo_verificado:
            return VerificacionCorreoResultado()
        if verificacion.usado or verificacion.fecha_expiracion <= ahora_utc():
            raise VerificacionInvalidaError()
        verificacion.usado = True
        if not usuario.correo_verificado:
            usuario.correo_verificado = True
            usuario.fecha_verificacion_correo = ahora_utc()
        self._uow.commit()
        return VerificacionCorreoResultado()

    def estado(self, id_usuario: uuid.UUID) -> EstadoVerificacionCorreo:
        usuario = self._usuario(id_usuario)
        return EstadoVerificacionCorreo(
            correo_verificado=usuario.correo_verificado,
            correo_enmascarado=enmascarar_correo(usuario.correo),
            puede_reenviar_en_segundos=0 if usuario.correo_verificado else self._espera(usuario),
        )

    def reenviar(self, id_usuario: uuid.UUID) -> MensajeGenerico:
        usuario = self._usuario(id_usuario)
        if usuario.correo_verificado:
            raise CorreoYaVerificadoError()
        espera = self._espera(usuario)
        if espera > 0:
            raise SolicitudesExcesivasError(cabeceras={"Retry-After": str(espera)})
        self._invalidar_anteriores(usuario)
        token = self._crear(usuario)
        self._uow.commit()
        self.enviar_sin_fallar(self._correo_verificacion(usuario, token))
        return MensajeGenerico(mensaje=MENSAJE_REENVIO)

    def _invalidar_anteriores(self, usuario: Usuario) -> None:
        ahora = ahora_utc()
        for anterior in self._verificaciones.listar_por_usuario(usuario.id_usuario):
            if not anterior.usado and anterior.fecha_expiracion > ahora:
                anterior.fecha_expiracion = ahora

    def _espera(self, usuario: Usuario) -> int:
        """Segundos hasta poder reenviar: espera mínima y tope por hora (usuario y dirección)."""
        espera_minima = 0
        ultima = self._verificaciones.obtener_ultima_por_usuario(usuario.id_usuario)
        if ultima is not None:
            espera_minima = segundos_hasta(
                ultima.fecha_creacion
                + timedelta(seconds=self._settings.verificacion_reenvio_espera_segundos)
            )
        return max(espera_minima, self._espera_por_frecuencia(usuario))

    def _espera_por_frecuencia(self, usuario: Usuario) -> int:
        fechas = self._verificaciones.fechas_envio_desde(
            usuario.id_usuario, usuario.correo_hash, ahora_utc() - VENTANA_ENVIOS
        )
        if len(fechas) < self._settings.verificacion_max_envios_por_hora:
            return 0
        return max(1, segundos_hasta(min(fechas) + VENTANA_ENVIOS))

    def _crear(self, usuario: Usuario) -> str:
        token = secrets.token_urlsafe(BYTES_TOKEN)
        ahora = ahora_utc()
        self._verificaciones.agregar(
            VerificacionCorreo(
                id_usuario=usuario.id_usuario,
                correo_hash=usuario.correo_hash,
                token_hash=sha256_hex(token),
                fecha_creacion=ahora,
                fecha_expiracion=ahora
                + timedelta(hours=self._settings.verificacion_correo_vigencia_horas),
                usado=False,
            )
        )
        return token

    def _correo_verificacion(self, usuario: Usuario, token: str) -> Correo:
        enlace = self._settings.frontend_url.rstrip("/") + RUTA_VERIFICAR.format(token=token)
        return plantillas.verificacion_correo(
            usuario.correo, enlace, self._settings.verificacion_correo_vigencia_horas
        )

    def _usuario(self, id_usuario: uuid.UUID) -> Usuario:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise TokenInvalidoError()
        return usuario
