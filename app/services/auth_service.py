import uuid

from app.core.config import Settings
from app.core.tiempo import ahora_utc, hoy_utc
from app.core.unit_of_work import UnitOfWork
from app.crypto.indice_ciego import IndiceCiego
from app.exceptions.base import (
    AutorizacionPendienteError,
    CorreoYaRegistradoError,
    CredencialesInvalidasError,
    CuentaDesactivadaError,
    TokenInvalidoError,
)
from app.models.enums import EstadoCuenta, EstadoSuscripcion, PlanSuscripcion
from app.models.perfil_aprendizaje import PerfilAprendizaje
from app.models.suscripcion import Suscripcion
from app.models.usuario import Usuario
from app.repositories.conversacion import PerfilAprendizajeRepository
from app.repositories.suscripcion import SuscripcionRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.auth import ContextoSolicitud, LoginEntrada, RegistroEntrada, SesionAutenticada
from app.schemas.perfil_aprendizaje import PreferenciasAprendizaje
from app.schemas.usuario import UsuarioPublico
from app.services.autorizacion_service import AutorizacionService
from app.services.consentimiento_service import ConsentimientoService
from app.services.limitador_service import LimitadorFrecuencia
from app.services.password_service import PasswordService
from app.services.presentacion import usuario_publico
from app.services.token_service import TokenService
from app.validators.edad import es_menor, validar_edad_minima, validar_fecha_nacimiento

PREFIJO_LIMITE_IP = "login-ip:"
PREFIJO_LIMITE_CORREO = "login-correo:"


class AuthService:
    """Registro, login y verificación de sesión y cuenta activa en cada petición."""

    def __init__(
        self,
        usuarios: UsuarioRepository,
        suscripciones: SuscripcionRepository,
        perfiles: PerfilAprendizajeRepository,
        passwords: PasswordService,
        tokens: TokenService,
        autorizaciones: AutorizacionService,
        consentimientos: ConsentimientoService,
        limitador: LimitadorFrecuencia,
        indice: IndiceCiego,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._usuarios = usuarios
        self._suscripciones = suscripciones
        self._perfiles = perfiles
        self._passwords = passwords
        self._tokens = tokens
        self._autorizaciones = autorizaciones
        self._consentimientos = consentimientos
        self._limitador = limitador
        self._indice = indice
        self._settings = settings
        self._uow = uow

    def registrar(self, entrada: RegistroEntrada, contexto: ContextoSolicitud) -> SesionAutenticada:
        self._consentimientos.validar_registro(entrada)
        self._validar_edad(entrada)
        # La edad la decide el servidor; de 13 a 17 años se exige el correo del acudiente.
        menor = es_menor(entrada.fecha_nacimiento, hoy_utc(), self._settings.edad_mayoria)
        correo_acudiente = (
            self._autorizaciones.validar_correo_acudiente(entrada.correo_acudiente, entrada.correo)
            if menor
            else None
        )
        correo_hash = self._indice.calcular(entrada.correo)
        if self._usuarios.existe_correo_hash(correo_hash):
            raise CorreoYaRegistradoError()
        usuario = self._crear_usuario(entrada, correo_hash, menor)
        self._crear_suscripcion_y_perfil(usuario, entrada.acepta_personalizacion)
        self._consentimientos.registrar_en_registro(usuario, entrada, menor, contexto)
        correo = (
            self._autorizaciones.crear_para_registro(usuario, correo_acudiente, contexto)
            if correo_acudiente
            else None
        )
        self._uow.commit()
        # Si el envío falla no se falla el registro: el estudiante puede reenviar.
        self._autorizaciones.enviar_sin_fallar(correo)
        return self._sesion(usuario)

    def autenticar(self, entrada: LoginEntrada, contexto: ContextoSolicitud) -> SesionAutenticada:
        claves_limite = (
            f"{PREFIJO_LIMITE_IP}{contexto.ip or ''}",
            f"{PREFIJO_LIMITE_CORREO}{entrada.correo}",
        )
        self._limitador.asegurar_permitido(*claves_limite)
        usuario = self._usuarios.obtener_por_correo_hash(self._indice.calcular(entrada.correo))
        if not self._passwords.verificar(
            entrada.contrasena, usuario.hash_contrasena if usuario else None
        ):
            self._limitador.registrar_fallo(*claves_limite)
            self._uow.commit()
            raise CredencialesInvalidasError()
        assert usuario is not None
        if not usuario.activo:
            raise CuentaDesactivadaError()
        self._reactivar_si_corresponde(usuario)
        self._uow.commit()
        return self._sesion(usuario)

    def validar_sesion(self, token: str | None) -> uuid.UUID:
        claims = self._tokens.leer(token)
        usuario = self._usuarios.obtener_por_id(claims.id_usuario)
        if usuario is None or usuario.version_token != claims.version_token:
            raise TokenInvalidoError()
        return usuario.id_usuario

    def asegurar_cuenta_activa(self, id_usuario: uuid.UUID) -> None:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise TokenInvalidoError()
        if not usuario.activo:
            raise CuentaDesactivadaError()
        if usuario.estado_cuenta == EstadoCuenta.PENDIENTE_AUTORIZACION:
            raise AutorizacionPendienteError()
        self._consentimientos.asegurar_vigente(usuario)

    def asegurar_sesion_activa(self, token: str | None) -> uuid.UUID:
        id_usuario = self.validar_sesion(token)
        self.asegurar_cuenta_activa(id_usuario)
        return id_usuario

    def obtener_actual(self, id_usuario: uuid.UUID) -> UsuarioPublico:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise TokenInvalidoError()
        return usuario_publico(usuario, hoy_utc(), self._settings.edad_mayoria)

    def _validar_edad(self, entrada: RegistroEntrada) -> None:
        hoy = hoy_utc()
        validar_fecha_nacimiento(entrada.fecha_nacimiento, hoy, self._settings.edad_maxima)
        validar_edad_minima(entrada.fecha_nacimiento, hoy, self._settings.edad_minima)

    def _crear_usuario(self, entrada: RegistroEntrada, correo_hash: str, menor: bool) -> Usuario:
        ahora = ahora_utc()
        return self._usuarios.agregar(
            Usuario(
                nombre=entrada.nombre,
                correo=entrada.correo,
                correo_hash=correo_hash,
                fecha_nacimiento=entrada.fecha_nacimiento,
                hash_contrasena=self._passwords.hashear(entrada.contrasena),
                nivel_educativo=entrada.nivel_educativo,
                tipo_nivel=entrada.tipo_nivel,
                estado_cuenta=(
                    EstadoCuenta.PENDIENTE_AUTORIZACION if menor else EstadoCuenta.ACTIVA
                ),
                fecha_aceptacion_tratamiento=ahora,
                version_texto_tratamiento=entrada.version_politica,
                version_token=0,
                fecha_registro=ahora,
                activo=True,
            )
        )

    def _crear_suscripcion_y_perfil(self, usuario: Usuario, personalizacion: bool) -> None:
        ahora = ahora_utc()
        self._suscripciones.agregar(
            Suscripcion(
                id_usuario=usuario.id_usuario,
                plan=PlanSuscripcion.GRATUITO,
                estado=EstadoSuscripcion.ACTIVA,
                fecha_inicio=ahora,
            )
        )
        self._perfiles.agregar(
            PerfilAprendizaje(
                id_usuario=usuario.id_usuario,
                personalizacion_activa=personalizacion,
                fecha_consentimiento=ahora if personalizacion else None,
                preferencias=PreferenciasAprendizaje().model_dump(mode="json"),
                version=1,
                total_interacciones=0,
                fecha_actualizacion=ahora,
            )
        )

    def _reactivar_si_corresponde(self, usuario: Usuario) -> None:
        if usuario.estado_cuenta != EstadoCuenta.PENDIENTE_AUTORIZACION:
            return
        adulto = not es_menor(usuario.fecha_nacimiento, hoy_utc(), self._settings.edad_mayoria)
        if adulto or self._autorizaciones.tiene_autorizacion_vigente(usuario.correo_hash):
            usuario.estado_cuenta = EstadoCuenta.ACTIVA

    def _sesion(self, usuario: Usuario) -> SesionAutenticada:
        publico = usuario_publico(usuario, hoy_utc(), self._settings.edad_mayoria)
        return SesionAutenticada(
            publico, self._tokens.emitir(usuario.id_usuario, usuario.version_token)
        )
