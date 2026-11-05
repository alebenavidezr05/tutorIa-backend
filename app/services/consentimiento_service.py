import uuid
from dataclasses import dataclass

from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.crypto.indice_ciego import IndiceCiego
from app.exceptions.base import DatoInvalidoError, RecursoNoEncontradoError
from app.models.consentimiento import Consentimiento
from app.models.enums import FinalidadConsentimiento, OtorgadoPor, TipoSolicitud
from app.models.solicitud_titular import SolicitudTitular
from app.models.usuario import Usuario
from app.repositories.conversacion import PerfilAprendizajeRepository
from app.repositories.seguridad import ConsentimientoRepository, SolicitudTitularRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.auth import ContextoSolicitud, RegistroEntrada
from app.schemas.privacidad import (
    AceptarPoliticaEntrada,
    CambioConsentimientoEntrada,
    ConsentimientoPublico,
)
from app.services.plazos import fecha_limite_solicitud
from app.services.politica_service import PoliticaService
from app.validators.consentimiento import (
    FINALIDADES_OBLIGATORIAS,
    FINALIDADES_OPCIONALES,
    validar_consentimientos_requeridos,
    validar_version_aceptada,
    validar_version_politica,
)

PREFIJO_IP = "ip:"
DETALLE_SUPRESION_POR_REVOCATORIA = (
    "Revocatoria de la autorización de tratamiento desde la aplicación."
)


@dataclass(frozen=True)
class Otorgamiento:
    finalidad: FinalidadConsentimiento
    otorgado: bool


class ConsentimientoService:
    """Registro de solo inserción de las autorizaciones por finalidad, con su prueba (§15.5)."""

    def __init__(
        self,
        consentimientos: ConsentimientoRepository,
        usuarios: UsuarioRepository,
        perfiles: PerfilAprendizajeRepository,
        solicitudes: SolicitudTitularRepository,
        politica: PoliticaService,
        indice: IndiceCiego,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._consentimientos = consentimientos
        self._usuarios = usuarios
        self._perfiles = perfiles
        self._solicitudes = solicitudes
        self._politica = politica
        self._indice = indice
        self._settings = settings
        self._uow = uow

    def validar_registro(self, entrada: RegistroEntrada) -> None:
        validar_version_politica(entrada.version_politica, self._settings.politica_version)
        validar_consentimientos_requeridos(
            {
                FinalidadConsentimiento.TRATAMIENTO: entrada.acepta_tratamiento,
                FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL: entrada.acepta_transferencia_internacional,
            }
        )

    def registrar_en_registro(
        self,
        usuario: Usuario,
        entrada: RegistroEntrada,
        es_menor: bool,
        contexto: ContextoSolicitud,
    ) -> None:
        otorgamientos = [
            Otorgamiento(FinalidadConsentimiento.TRATAMIENTO, entrada.acepta_tratamiento),
            Otorgamiento(
                FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL,
                entrada.acepta_transferencia_internacional,
            ),
            Otorgamiento(FinalidadConsentimiento.PERSONALIZACION, entrada.acepta_personalizacion),
            Otorgamiento(FinalidadConsentimiento.COMUNICACIONES, entrada.acepta_comunicaciones),
        ]
        if es_menor:
            otorgamientos.append(
                Otorgamiento(FinalidadConsentimiento.OPINION_MENOR, entrada.entiende_datos_menor)
            )
        for o in otorgamientos:
            self.registrar(
                usuario.id_usuario, usuario.correo_hash, o, OtorgadoPor.TITULAR, contexto
            )

    def registrar_por_acudiente(
        self,
        id_autorizacion: uuid.UUID,
        correo_estudiante_hash: str,
        otorgamientos: list[Otorgamiento],
        contexto: ContextoSolicitud,
        texto_sha256: str,
    ) -> None:
        """El acudiente confirma la frase exacta que vio: su huella es la prueba registrada."""
        for o in otorgamientos:
            self.registrar(
                None,
                correo_estudiante_hash,
                o,
                OtorgadoPor.REPRESENTANTE_LEGAL,
                contexto,
                id_autorizacion,
                texto_sha256,
            )

    def registrar(
        self,
        id_usuario: uuid.UUID | None,
        correo_hash: str,
        otorgamiento: Otorgamiento,
        otorgado_por: OtorgadoPor,
        contexto: ContextoSolicitud,
        id_autorizacion: uuid.UUID | None = None,
        texto_sha256: str | None = None,
    ) -> None:
        self._consentimientos.insertar(
            Consentimiento(
                id_usuario=id_usuario,
                id_autorizacion=id_autorizacion,
                correo_hash=correo_hash,
                finalidad=otorgamiento.finalidad,
                otorgado=otorgamiento.otorgado,
                otorgado_por=otorgado_por,
                version_politica=self._settings.politica_version,
                texto_sha256=texto_sha256 or self._politica.huella(otorgamiento.finalidad),
                ip_hash=self.hash_ip(contexto.ip),
                fecha=ahora_utc(),
            )
        )

    def cambiar(
        self,
        id_usuario: uuid.UUID,
        entrada: CambioConsentimientoEntrada,
        contexto: ContextoSolicitud,
    ) -> list[ConsentimientoPublico]:
        validar_version_politica(entrada.version_politica, self._settings.politica_version)
        usuario = self._usuario(id_usuario)
        self._validar_finalidad_modificable(entrada)
        otorgamiento = Otorgamiento(entrada.finalidad, entrada.otorgado)
        self.registrar(id_usuario, usuario.correo_hash, otorgamiento, OtorgadoPor.TITULAR, contexto)
        self._aplicar_efectos(usuario, otorgamiento)
        self._uow.commit()
        return self.estado_actual(id_usuario)

    def aceptar_politica(
        self, id_usuario: uuid.UUID, entrada: AceptarPoliticaEntrada, contexto: ContextoSolicitud
    ) -> list[ConsentimientoPublico]:
        validar_version_politica(entrada.version_politica, self._settings.politica_version)
        validar_consentimientos_requeridos(
            {
                FinalidadConsentimiento.TRATAMIENTO: entrada.acepta_tratamiento,
                FinalidadConsentimiento.TRANSFERENCIA_INTERNACIONAL: entrada.acepta_transferencia_internacional,
            }
        )
        usuario = self._usuario(id_usuario)
        for finalidad in FINALIDADES_OBLIGATORIAS:
            self.registrar(
                id_usuario,
                usuario.correo_hash,
                Otorgamiento(finalidad, True),
                OtorgadoPor.TITULAR,
                contexto,
            )
        usuario.version_texto_tratamiento = self._settings.politica_version
        usuario.fecha_aceptacion_tratamiento = ahora_utc()
        self._uow.commit()
        return self.estado_actual(id_usuario)

    def estado_actual(self, id_usuario: uuid.UUID) -> list[ConsentimientoPublico]:
        ultimos: dict[FinalidadConsentimiento, Consentimiento] = {}
        for fila in self._consentimientos.listar_por_usuario(id_usuario):
            ultimos[fila.finalidad] = fila
        return [
            ConsentimientoPublico(
                finalidad=f.finalidad,
                otorgado=f.otorgado,
                otorgado_por=f.otorgado_por,
                version_politica=f.version_politica,
                fecha=f.fecha,
            )
            for f in ultimos.values()
        ]

    def asegurar_vigente(self, usuario: Usuario) -> None:
        validar_version_aceptada(
            usuario.version_texto_tratamiento, self._settings.politica_version_minima_aceptada
        )

    def hash_ip(self, ip: str | None) -> str | None:
        return self._indice.calcular(f"{PREFIJO_IP}{ip}") if ip else None

    def _usuario(self, id_usuario: uuid.UUID) -> Usuario:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        return usuario

    @staticmethod
    def _validar_finalidad_modificable(entrada: CambioConsentimientoEntrada) -> None:
        es_opcional = entrada.finalidad in FINALIDADES_OPCIONALES
        es_revocatoria_obligatoria = (
            entrada.finalidad in FINALIDADES_OBLIGATORIAS and not entrada.otorgado
        )
        if not (es_opcional or es_revocatoria_obligatoria):
            raise DatoInvalidoError("Esa autorización no se puede modificar desde aquí.")

    def _aplicar_efectos(self, usuario: Usuario, otorgamiento: Otorgamiento) -> None:
        if otorgamiento.finalidad == FinalidadConsentimiento.PERSONALIZACION:
            self._cambiar_personalizacion(usuario.id_usuario, otorgamiento.otorgado)
        if otorgamiento.finalidad in FINALIDADES_OBLIGATORIAS:
            self._crear_solicitud_supresion(usuario.id_usuario)

    def _cambiar_personalizacion(self, id_usuario: uuid.UUID, activa: bool) -> None:
        perfil = self._perfiles.obtener_por_usuario(id_usuario)
        if perfil is None:
            return
        perfil.personalizacion_activa = activa
        perfil.fecha_consentimiento = ahora_utc() if activa else perfil.fecha_consentimiento

    def _crear_solicitud_supresion(self, id_usuario: uuid.UUID) -> None:
        # Revocar una autorización obligatoria equivale a pedir la supresión de los datos (§6.7).
        ahora = ahora_utc()
        self._solicitudes.crear(
            SolicitudTitular(
                id_usuario=id_usuario,
                tipo=TipoSolicitud.SUPRESION,
                detalle=DETALLE_SUPRESION_POR_REVOCATORIA,
                fecha_recepcion=ahora,
                fecha_limite=fecha_limite_solicitud(
                    TipoSolicitud.SUPRESION, ahora.date(), self._settings
                ),
            )
        )
