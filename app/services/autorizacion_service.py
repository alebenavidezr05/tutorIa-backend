import secrets
from datetime import timedelta

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.correo import plantillas
from app.correo.base import Correo, CorreoClient
from app.crypto.indice_ciego import IndiceCiego, sha256_hex
from app.exceptions.base import (
    AutorizacionInvalidaError,
    ConsentimientoRequeridoError,
    DatoInvalidoError,
    SolicitudesExcesivasError,
)
from app.models.autorizacion_acudiente import AutorizacionAcudiente
from app.models.enums import EstadoAutorizacion, EstadoCuenta, FinalidadConsentimiento, OtorgadoPor
from app.repositories.autorizacion import AutorizacionRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.auth import ContextoSolicitud
from app.schemas.autorizacion import (
    AutorizacionPublica,
    MensajeGenerico,
    RevocarAutorizacionEntrada,
    SolicitudAutorizacionEntrada,
    TokenAutorizacionEntrada,
)
from app.services.consentimiento_service import ConsentimientoService, Otorgamiento
from app.services.supresor_datos import SupresorDatos
from app.validators.consentimiento import (
    validar_consentimientos_requeridos,
    validar_version_politica,
)
from app.validators.privacidad import enmascarar_correo

BYTES_TOKEN = 32
VENTANA_SOLICITUDES = timedelta(hours=1)
MENSAJE_SOLICITUD = (
    "Si los datos son correctos, enviamos un correo al acudiente para que confirme la autorización."
)
RUTA_CONFIRMAR = "/autorizacion/confirmar#token={token}"
RUTA_REVOCAR = "/autorizacion/revocar#token={token}"
ESTADOS_REVOCABLES = {EstadoAutorizacion.PENDIENTE_VERIFICACION, EstadoAutorizacion.AUTORIZADA}


class AutorizacionService:
    """Autorización del representante legal por correo verificado. El acudiente no tiene cuenta:
    se identifica con un token de un solo propósito que solo viaja en el fragmento del enlace."""

    def __init__(
        self,
        autorizaciones: AutorizacionRepository,
        usuarios: UsuarioRepository,
        consentimientos: ConsentimientoService,
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
        self._supresor = supresor
        self._correo = correo
        self._almacen = almacen
        self._indice = indice
        self._settings = settings
        self._uow = uow

    def solicitar(
        self, entrada: SolicitudAutorizacionEntrada, contexto: ContextoSolicitud
    ) -> MensajeGenerico:
        self._validar_solicitud(entrada)
        hash_acudiente = self._indice.calcular(entrada.correo_acudiente)
        hash_estudiante = self._indice.calcular(entrada.correo_estudiante)
        self._asegurar_frecuencia(hash_acudiente, hash_estudiante)
        self._vencer_pendientes(hash_estudiante)
        token = secrets.token_urlsafe(BYTES_TOKEN)
        autorizacion = self._crear(entrada, hash_acudiente, hash_estudiante, token, contexto)
        self._consentimientos.registrar_por_acudiente(
            autorizacion.id_autorizacion, hash_estudiante, self._otorgamientos(entrada), contexto
        )
        self._uow.commit()
        self._correo.enviar(self._correo_solicitud(entrada, token))
        return MensajeGenerico(mensaje=MENSAJE_SOLICITUD)

    def consultar(self, entrada: TokenAutorizacionEntrada) -> AutorizacionPublica:
        return self._publica(self._vigente_por_token(entrada.token))

    def confirmar(self, entrada: TokenAutorizacionEntrada) -> AutorizacionPublica:
        autorizacion = self._vigente_por_token(entrada.token)
        if autorizacion.estado == EstadoAutorizacion.AUTORIZADA:
            return self._publica(autorizacion)
        if autorizacion.estado != EstadoAutorizacion.PENDIENTE_VERIFICACION:
            raise AutorizacionInvalidaError()
        autorizacion.estado = EstadoAutorizacion.AUTORIZADA
        autorizacion.fecha_verificacion = ahora_utc()
        self._activar_estudiante(autorizacion.correo_estudiante_hash)
        self._uow.commit()
        self._correo.enviar(
            plantillas.autorizacion_confirmada(
                autorizacion.correo_acudiente,
                enmascarar_correo(autorizacion.correo_estudiante),
                self._enlace(RUTA_REVOCAR, entrada.token),
            )
        )
        return self._publica(autorizacion)

    def revocar(
        self, entrada: RevocarAutorizacionEntrada, contexto: ContextoSolicitud
    ) -> AutorizacionPublica:
        autorizacion = self._vigente_por_token(entrada.token)
        if autorizacion.estado not in ESTADOS_REVOCABLES:
            raise AutorizacionInvalidaError()
        autorizacion.estado = EstadoAutorizacion.REVOCADA
        autorizacion.fecha_revocacion = ahora_utc()
        self._registrar_revocatoria(autorizacion, contexto)
        claves = self._bloquear_estudiante(
            autorizacion.correo_estudiante_hash, entrada.eliminar_datos
        )
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(claves)
        return self._publica(autorizacion)

    def tiene_autorizacion_vigente(self, correo_estudiante_hash: str) -> bool:
        return self._vigente_para(correo_estudiante_hash) is not None

    def permite_compras(self, correo_estudiante_hash: str) -> bool:
        autorizacion = self._vigente_para(correo_estudiante_hash)
        return autorizacion is not None and autorizacion.permite_compras

    def _vigente_para(self, correo_estudiante_hash: str) -> AutorizacionAcudiente | None:
        desde = ahora_utc() - timedelta(days=self._settings.autorizacion_expira_dias)
        return self._autorizaciones.obtener_vigente_por_estudiante(correo_estudiante_hash, desde)

    def _validar_solicitud(self, entrada: SolicitudAutorizacionEntrada) -> None:
        if entrada.correo_acudiente == entrada.correo_estudiante:
            raise DatoInvalidoError("El correo del acudiente debe ser distinto al del estudiante.")
        if not entrada.declara_representante_legal:
            raise ConsentimientoRequeridoError("Debes declarar que eres el representante legal.")
        validar_version_politica(entrada.version_politica, self._settings.politica_version)
        validar_consentimientos_requeridos(
            {
                FinalidadConsentimiento.TRATAMIENTO: entrada.acepta_tratamiento,
                FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL: entrada.acepta_transferencia_internacional,
            }
        )

    def _asegurar_frecuencia(self, *hashes: str) -> None:
        desde = ahora_utc() - VENTANA_SOLICITUDES
        maximo = self._settings.autorizacion_max_solicitudes_por_hora
        if any(self._autorizaciones.contar_solicitudes_desde(h, desde) >= maximo for h in hashes):
            raise SolicitudesExcesivasError()

    def _vencer_pendientes(self, hash_estudiante: str) -> None:
        for pendiente in self._autorizaciones.listar_pendientes_por_estudiante(hash_estudiante):
            pendiente.estado = EstadoAutorizacion.VENCIDA

    def _crear(
        self,
        entrada: SolicitudAutorizacionEntrada,
        hash_acudiente: str,
        hash_estudiante: str,
        token: str,
        contexto: ContextoSolicitud,
    ) -> AutorizacionAcudiente:
        ahora = ahora_utc()
        return self._autorizaciones.agregar(
            AutorizacionAcudiente(
                correo_acudiente=entrada.correo_acudiente,
                correo_acudiente_hash=hash_acudiente,
                correo_estudiante=entrada.correo_estudiante,
                correo_estudiante_hash=hash_estudiante,
                estado=EstadoAutorizacion.PENDIENTE_VERIFICACION,
                permite_compras=entrada.permite_compras,
                token_hash=sha256_hex(token),
                version_texto=entrada.version_politica,
                ip_hash=self._consentimientos.hash_ip(contexto.ip),
                fecha_solicitud=ahora,
                fecha_expiracion_token=ahora
                + timedelta(hours=self._settings.autorizacion_token_horas),
            )
        )

    @staticmethod
    def _otorgamientos(entrada: SolicitudAutorizacionEntrada) -> list[Otorgamiento]:
        otorgamientos = [
            Otorgamiento(FinalidadConsentimiento.TRATAMIENTO, True),
            Otorgamiento(FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL, True),
        ]
        if entrada.permite_compras:
            otorgamientos.append(Otorgamiento(FinalidadConsentimiento.COMPRAS_MENOR, True))
        return otorgamientos

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
        for finalidad in (
            FinalidadConsentimiento.TRATAMIENTO,
            FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL,
        ):
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

    def _correo_solicitud(self, entrada: SolicitudAutorizacionEntrada, token: str) -> Correo:
        return plantillas.solicitud_autorizacion(
            entrada.correo_acudiente,
            enmascarar_correo(entrada.correo_estudiante),
            self._enlace(RUTA_CONFIRMAR, token),
            self._settings.autorizacion_token_horas,
            self._enlace(RUTA_REVOCAR, token),
        )

    def _enlace(self, ruta: str, token: str) -> str:
        return self._settings.frontend_url.rstrip("/") + ruta.format(token=token)

    @staticmethod
    def _publica(autorizacion: AutorizacionAcudiente) -> AutorizacionPublica:
        return AutorizacionPublica(
            estado=autorizacion.estado,
            correo_estudiante_enmascarado=enmascarar_correo(autorizacion.correo_estudiante),
            permite_compras=autorizacion.permite_compras,
            fecha_expiracion_token=autorizacion.fecha_expiracion_token,
        )
