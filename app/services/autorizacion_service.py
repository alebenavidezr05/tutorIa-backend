import logging
import math
import secrets
import uuid
from datetime import datetime, timedelta

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.correo import plantillas
from app.correo.base import Correo, CorreoClient
from app.correo.tolerante import correo_valido, enviar_sin_fallar
from app.crypto.indice_ciego import IndiceCiego, sha256_hex
from app.exceptions.base import (
    AutorizacionInvalidaError,
    CorreoAcudienteInvalidoError,
    CorreoAcudienteRequeridoError,
    OperacionNoPermitidaError,
    SolicitudesExcesivasError,
)
from app.models.autorizacion_acudiente import AutorizacionAcudiente
from app.models.enums import (
    EstadoAutorizacion,
    EstadoAutorizacionEstudiante,
    EstadoCuenta,
    FinalidadConsentimiento,
    OtorgadoPor,
)
from app.models.usuario import Usuario
from app.repositories.autorizacion import AutorizacionRepository
from app.repositories.usuario import UsuarioRepository
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
from app.services.consentimiento_service import ConsentimientoService, Otorgamiento
from app.services.politica_service import PoliticaService
from app.services.supresor_datos import SupresorDatos
from app.validators.consentimiento import validar_version_politica
from app.validators.privacidad import enmascarar_correo
from app.validators.usuario import normalizar_correo

logger = logging.getLogger(__name__)

BYTES_TOKEN = 32
VENTANA_SOLICITUDES = timedelta(hours=1)
MENSAJE_REENVIO = "Enviamos un nuevo correo a tu acudiente para que revise la autorización."
RUTA_CONFIRMAR = "/autorizacion/confirmar#token={token}"
RUTA_REVOCAR = "/autorizacion/revocar#token={token}"
ESTADOS_REVOCABLES = {EstadoAutorizacion.PENDIENTE_VERIFICACION, EstadoAutorizacion.AUTORIZADA}
FINALIDADES_ACUDIENTE = (
    FinalidadConsentimiento.TRATAMIENTO,
    FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL,
)
ESTADO_ESTUDIANTE = {
    EstadoAutorizacion.PENDIENTE_VERIFICACION: EstadoAutorizacionEstudiante.PENDIENTE,
    EstadoAutorizacion.AUTORIZADA: EstadoAutorizacionEstudiante.AUTORIZADA,
    EstadoAutorizacion.RECHAZADA: EstadoAutorizacionEstudiante.RECHAZADA,
    EstadoAutorizacion.REVOCADA: EstadoAutorizacionEstudiante.REVOCADA,
    EstadoAutorizacion.VENCIDA: EstadoAutorizacionEstudiante.EXPIRADA,
}


def primer_nombre(nombre: str) -> str:
    return nombre.split()[0] if nombre.strip() else ""


class AutorizacionService:
    """Autorización del representante legal, iniciada por el estudiante al registrarse. El
    acudiente no tiene cuenta: se identifica con un token de un solo propósito que solo viaja en
    el fragmento del enlace. No hay ruta pública que envíe correos sin sesión ni token."""

    def __init__(
        self,
        autorizaciones: AutorizacionRepository,
        usuarios: UsuarioRepository,
        consentimientos: ConsentimientoService,
        politica: PoliticaService,
        supresor: SupresorDatos,
        correo: CorreoClient,
        almacen: Almacen,
        indice: IndiceCiego,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._autorizaciones = autorizaciones
        self._usuarios = usuarios
        self._consentimientos = consentimientos
        self._politica = politica
        self._supresor = supresor
        self._correo = correo
        self._almacen = almacen
        self._indice = indice
        self._settings = settings
        self._uow = uow

    # Estudiante: registro, estado y reenvío
    @staticmethod
    def validar_correo_acudiente(correo_acudiente: str | None, correo_estudiante: str) -> str:
        if correo_acudiente is None or not correo_acudiente.strip():
            raise CorreoAcudienteRequeridoError()
        correo = correo_valido(correo_acudiente.strip())
        if correo is None:
            raise CorreoAcudienteInvalidoError()
        normalizado = normalizar_correo(correo)
        if normalizado == normalizar_correo(correo_estudiante):
            raise CorreoAcudienteInvalidoError()
        return normalizado

    def crear_para_registro(
        self, estudiante: Usuario, correo_acudiente: str, contexto: ContextoSolicitud
    ) -> Correo | None:
        """Crea la solicitud dentro de la transacción del registro (no confirma). Devuelve el
        correo para enviarlo después del commit, o None si ese acudiente superó el tope por hora."""
        hash_acudiente = self._indice.calcular(correo_acudiente)
        excedido = self._espera_por_frecuencia(hash_acudiente) > 0
        autorizacion, token = self._crear(estudiante, correo_acudiente, hash_acudiente, contexto)
        if excedido:
            logger.warning("autorizacion_correo_omitido motivo=frecuencia_acudiente")
            return None
        return self._correo_solicitud(estudiante, autorizacion, token)

    def enviar_sin_fallar(self, correo: Correo | None) -> None:
        """El envío ocurre tras el commit; si falla, el estudiante puede usar «Reenviar»."""
        if correo is not None:
            enviar_sin_fallar(self._correo, correo, "autorizacion_correo_no_enviado")

    def mia(self, id_usuario: uuid.UUID) -> MiAutorizacion:
        estudiante = self._estudiante(id_usuario)
        ultima = self._autorizaciones.obtener_ultima_por_estudiante(estudiante.correo_hash)
        return MiAutorizacion(
            estado=self._estado_estudiante(ultima),
            correo_acudiente_enmascarado=(
                enmascarar_correo(ultima.correo_acudiente) if ultima else None
            ),
            puede_reenviar_en_segundos=self._espera_reenvio(estudiante.correo_hash, ultima),
        )

    def reenviar(
        self,
        id_usuario: uuid.UUID,
        entrada: ReenviarAutorizacionEntrada,
        contexto: ContextoSolicitud,
    ) -> MensajeGenerico:
        estudiante = self._estudiante(id_usuario)
        if estudiante.estado_cuenta != EstadoCuenta.PENDIENTE_AUTORIZACION:
            raise OperacionNoPermitidaError("Tu cuenta no necesita una nueva autorización.")
        ultima = self._autorizaciones.obtener_ultima_por_estudiante(estudiante.correo_hash)
        correo_acudiente = self._destino_reenvio(entrada, estudiante, ultima)
        hash_acudiente = self._indice.calcular(correo_acudiente)
        self._asegurar_puede_reenviar(estudiante.correo_hash, hash_acudiente, ultima)
        self._vencer_pendientes(estudiante.correo_hash)
        autorizacion, token = self._crear(estudiante, correo_acudiente, hash_acudiente, contexto)
        self._uow.commit()
        self.enviar_sin_fallar(self._correo_solicitud(estudiante, autorizacion, token))
        return MensajeGenerico(mensaje=MENSAJE_REENVIO)

    # Acudiente: enlace con token
    def consultar(self, entrada: TokenAutorizacionEntrada) -> AutorizacionPublica:
        return self._publica(self._vigente_por_token(entrada.token))

    def confirmar(
        self, entrada: ConfirmarAutorizacionEntrada, contexto: ContextoSolicitud
    ) -> AutorizacionPublica:
        autorizacion = self._vigente_por_token(entrada.token)
        if autorizacion.estado == EstadoAutorizacion.AUTORIZADA:
            return self._publica(autorizacion)
        if autorizacion.estado != EstadoAutorizacion.PENDIENTE_VERIFICACION:
            raise AutorizacionInvalidaError()
        validar_version_politica(entrada.version_politica, self._settings.politica_version)
        autorizacion.estado = EstadoAutorizacion.AUTORIZADA
        autorizacion.fecha_verificacion = ahora_utc()
        autorizacion.version_texto = self._settings.politica_version
        self._consentimientos.registrar_por_acudiente(
            autorizacion.id_autorizacion,
            autorizacion.correo_estudiante_hash,
            [Otorgamiento(f, True) for f in FINALIDADES_ACUDIENTE],
            contexto,
            self._politica.huella_autorizacion_acudiente(),
        )
        self._activar_estudiante(autorizacion.correo_estudiante_hash)
        self._uow.commit()
        self.enviar_sin_fallar(
            plantillas.autorizacion_confirmada(
                autorizacion.correo_acudiente,
                enmascarar_correo(autorizacion.correo_estudiante),
                self._enlace(RUTA_REVOCAR, entrada.token),
            )
        )
        return self._publica(autorizacion)

    def rechazar(self, entrada: TokenAutorizacionEntrada) -> AutorizacionPublica:
        autorizacion = self._vigente_por_token(entrada.token)
        if autorizacion.estado == EstadoAutorizacion.RECHAZADA:
            return self._publica(autorizacion)
        if autorizacion.estado != EstadoAutorizacion.PENDIENTE_VERIFICACION:
            raise AutorizacionInvalidaError()
        autorizacion.estado = EstadoAutorizacion.RECHAZADA
        autorizacion.fecha_verificacion = ahora_utc()
        self._uow.commit()
        return self._publica(autorizacion)

    def revocar(
        self, entrada: RevocarAutorizacionEntrada, contexto: ContextoSolicitud
    ) -> AutorizacionPublica:
        autorizacion = self._vigente_por_token(entrada.token)
        if autorizacion.estado not in ESTADOS_REVOCABLES:
            raise AutorizacionInvalidaError()
        # Se arma la respuesta antes de una posible supresión, que anonimiza el nombre.
        publica = self._publica(autorizacion, EstadoAutorizacion.REVOCADA)
        autorizacion.estado = EstadoAutorizacion.REVOCADA
        autorizacion.fecha_revocacion = ahora_utc()
        self._registrar_revocatoria(autorizacion, contexto)
        claves = self._bloquear_estudiante(
            autorizacion.correo_estudiante_hash, entrada.eliminar_datos
        )
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(claves)
        return publica

    # Consultas de otros services
    def tiene_autorizacion_vigente(self, correo_estudiante_hash: str) -> bool:
        return self._vigente_para(correo_estudiante_hash) is not None

    def permite_compras(self, correo_estudiante_hash: str) -> bool:
        autorizacion = self._vigente_para(correo_estudiante_hash)
        return autorizacion is not None and autorizacion.permite_compras

    def _vigente_para(self, correo_estudiante_hash: str) -> AutorizacionAcudiente | None:
        desde = ahora_utc() - timedelta(days=self._settings.autorizacion_expira_dias)
        return self._autorizaciones.obtener_vigente_por_estudiante(correo_estudiante_hash, desde)

    # Reglas de reenvío
    def _destino_reenvio(
        self,
        entrada: ReenviarAutorizacionEntrada,
        estudiante: Usuario,
        ultima: AutorizacionAcudiente | None,
    ) -> str:
        if entrada.correo_acudiente is None and ultima is not None:
            return ultima.correo_acudiente
        return self.validar_correo_acudiente(entrada.correo_acudiente, estudiante.correo)

    def _asegurar_puede_reenviar(
        self, hash_estudiante: str, hash_acudiente: str, ultima: AutorizacionAcudiente | None
    ) -> None:
        espera = max(
            self._espera_reenvio(hash_estudiante, ultima),
            self._espera_por_frecuencia(hash_acudiente),
            self._espera_por_rechazo(hash_estudiante, hash_acudiente),
        )
        if espera > 0:
            raise SolicitudesExcesivasError(cabeceras={"Retry-After": str(espera)})

    def _espera_reenvio(self, hash_estudiante: str, ultima: AutorizacionAcudiente | None) -> int:
        """Segundos hasta poder reenviar: espera mínima entre envíos y tope por hora."""
        espera_minima = 0
        if ultima is not None:
            disponible = ultima.fecha_solicitud + timedelta(
                seconds=self._settings.autorizacion_reenvio_espera_segundos
            )
            espera_minima = _segundos_hasta(disponible)
        return max(espera_minima, self._espera_por_frecuencia(hash_estudiante))

    def _espera_por_frecuencia(self, correo_hash: str) -> int:
        desde = ahora_utc() - VENTANA_SOLICITUDES
        fechas = self._autorizaciones.fechas_solicitud_desde(correo_hash, desde)
        if len(fechas) < self._settings.autorizacion_max_solicitudes_por_hora:
            return 0
        return max(1, _segundos_hasta(min(fechas) + VENTANA_SOLICITUDES))

    def _espera_por_rechazo(self, hash_estudiante: str, hash_acudiente: str) -> int:
        bloqueo = timedelta(days=self._settings.autorizacion_bloqueo_rechazo_dias)
        rechazo = self._autorizaciones.obtener_rechazo_desde(
            hash_estudiante, hash_acudiente, ahora_utc() - bloqueo
        )
        if rechazo is None or rechazo.fecha_verificacion is None:
            return 0
        return max(1, _segundos_hasta(rechazo.fecha_verificacion + bloqueo))

    # Apoyo
    def _estudiante(self, id_usuario: uuid.UUID) -> Usuario:
        estudiante = self._usuarios.obtener_por_id(id_usuario)
        if estudiante is None:
            raise AutorizacionInvalidaError()
        return estudiante

    @staticmethod
    def _estado_estudiante(ultima: AutorizacionAcudiente | None) -> EstadoAutorizacionEstudiante:
        if ultima is None:
            return EstadoAutorizacionEstudiante.SIN_SOLICITUD
        pendiente = ultima.estado == EstadoAutorizacion.PENDIENTE_VERIFICACION
        if pendiente and ultima.fecha_expiracion_token < ahora_utc():
            return EstadoAutorizacionEstudiante.EXPIRADA
        return ESTADO_ESTUDIANTE[ultima.estado]

    def _vencer_pendientes(self, hash_estudiante: str) -> None:
        for pendiente in self._autorizaciones.listar_pendientes_por_estudiante(hash_estudiante):
            pendiente.estado = EstadoAutorizacion.VENCIDA

    def _crear(
        self,
        estudiante: Usuario,
        correo_acudiente: str,
        hash_acudiente: str,
        contexto: ContextoSolicitud,
    ) -> tuple[AutorizacionAcudiente, str]:
        token = secrets.token_urlsafe(BYTES_TOKEN)
        ahora = ahora_utc()
        autorizacion = self._autorizaciones.agregar(
            AutorizacionAcudiente(
                correo_acudiente=correo_acudiente,
                correo_acudiente_hash=hash_acudiente,
                correo_estudiante=estudiante.correo,
                correo_estudiante_hash=estudiante.correo_hash,
                estado=EstadoAutorizacion.PENDIENTE_VERIFICACION,
                permite_compras=False,
                token_hash=sha256_hex(token),
                version_texto=self._settings.politica_version,
                ip_hash=self._consentimientos.hash_ip(contexto.ip),
                fecha_solicitud=ahora,
                fecha_expiracion_token=ahora
                + timedelta(hours=self._settings.autorizacion_token_horas),
            )
        )
        return autorizacion, token

    def _vigente_por_token(self, token: str) -> AutorizacionAcudiente:
        autorizacion = self._autorizaciones.obtener_por_token_hash(sha256_hex(token))
        if autorizacion is None or autorizacion.estado == EstadoAutorizacion.VENCIDA:
            raise AutorizacionInvalidaError()
        pendiente = autorizacion.estado == EstadoAutorizacion.PENDIENTE_VERIFICACION
        if pendiente and autorizacion.fecha_expiracion_token < ahora_utc():
            raise AutorizacionInvalidaError()
        return autorizacion

    def _activar_estudiante(self, correo_estudiante_hash: str) -> None:
        estudiante = self._usuarios.obtener_por_correo_hash(correo_estudiante_hash)
        if (
            estudiante is not None
            and estudiante.estado_cuenta == EstadoCuenta.PENDIENTE_AUTORIZACION
        ):
            estudiante.estado_cuenta = EstadoCuenta.ACTIVA

    def _registrar_revocatoria(
        self, autorizacion: AutorizacionAcudiente, contexto: ContextoSolicitud
    ) -> None:
        for finalidad in FINALIDADES_ACUDIENTE:
            self._consentimientos.registrar(
                None,
                autorizacion.correo_estudiante_hash,
                Otorgamiento(finalidad, False),
                OtorgadoPor.REPRESENTANTE_LEGAL,
                contexto,
                autorizacion.id_autorizacion,
            )

    def _bloquear_estudiante(self, correo_estudiante_hash: str, eliminar_datos: bool) -> list[str]:
        estudiante = self._usuarios.obtener_por_correo_hash(correo_estudiante_hash)
        if estudiante is None:
            return []
        estudiante.estado_cuenta = EstadoCuenta.PENDIENTE_AUTORIZACION
        estudiante.version_token += 1
        return self._supresor.suprimir(estudiante) if eliminar_datos else []

    def _correo_solicitud(
        self, estudiante: Usuario, autorizacion: AutorizacionAcudiente, token: str
    ) -> Correo:
        return plantillas.solicitud_autorizacion(
            autorizacion.correo_acudiente,
            primer_nombre(estudiante.nombre),
            enmascarar_correo(estudiante.correo),
            self._enlace(RUTA_CONFIRMAR, token),
            self._settings.autorizacion_token_horas,
        )

    def _enlace(self, ruta: str, token: str) -> str:
        return self._settings.frontend_url.rstrip("/") + ruta.format(token=token)

    def _publica(
        self, autorizacion: AutorizacionAcudiente, estado: EstadoAutorizacion | None = None
    ) -> AutorizacionPublica:
        estudiante = self._usuarios.obtener_por_correo_hash(autorizacion.correo_estudiante_hash)
        return AutorizacionPublica(
            estado=estado or autorizacion.estado,
            nombre_estudiante=primer_nombre(estudiante.nombre) if estudiante else "",
            correo_estudiante_enmascarado=enmascarar_correo(autorizacion.correo_estudiante),
            texto_consentimiento=self._politica.texto_autorizacion_acudiente(),
            version_politica=self._settings.politica_version,
            permite_compras=autorizacion.permite_compras,
            fecha_expiracion_token=autorizacion.fecha_expiracion_token,
        )


def _segundos_hasta(momento: datetime) -> int:
    return max(0, math.ceil((momento - ahora_utc()).total_seconds()))
