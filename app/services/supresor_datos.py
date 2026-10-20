import secrets
import uuid
from datetime import date

from app.core.tiempo import ahora_utc
from app.crypto.indice_ciego import sha256_hex
from app.models.archivo_adjunto import ArchivoAdjunto
from app.models.enums import EstadoArchivo
from app.models.usuario import Usuario
from app.repositories.archivo import ArchivoRepository
from app.repositories.conversacion import (
    ConversacionRepository,
    EventoAprendizajeRepository,
    PerfilAprendizajeRepository,
)
from app.repositories.diagnostico import SesionDiagnosticoRepository
from app.repositories.seguridad import AlertaSeguridadRepository, ConsentimientoRepository

NOMBRE_ANONIMO = "Usuario eliminado"
DOMINIO_ANONIMO = "eliminado.invalid"
FECHA_NACIMIENTO_NEUTRA = date(1900, 1, 1)
# Un hash que bcrypt nunca acepta: la cuenta anonimizada no puede volver a iniciar sesión.
HASH_INUTILIZABLE = "!" * 60
NOMBRE_ARCHIVO_ELIMINADO = "eliminado"


class SupresorDatos:
    """Borra los datos de estudio de un titular y anonimiza su fila de usuario. No confirma: lo
    hace el caso de uso que lo invoca. Conserva la prueba de consentimiento y los pagos."""

    def __init__(
        self,
        conversaciones: ConversacionRepository,
        sesiones: SesionDiagnosticoRepository,
        perfiles: PerfilAprendizajeRepository,
        eventos: EventoAprendizajeRepository,
        archivos: ArchivoRepository,
        alertas: AlertaSeguridadRepository,
        consentimientos: ConsentimientoRepository,
    ) -> None:
        self._conversaciones = conversaciones
        self._sesiones = sesiones
        self._perfiles = perfiles
        self._eventos = eventos
        self._archivos = archivos
        self._alertas = alertas
        self._consentimientos = consentimientos

    def suprimir(self, usuario: Usuario) -> list[str]:
        """Devuelve las claves del almacén que se deben borrar después del commit."""
        claves = self.marcar_archivos_eliminados(
            self._archivos.listar_por_usuario(usuario.id_usuario)
        )
        self._borrar_estudio(usuario.id_usuario)
        self._desvincular_evidencia(usuario.id_usuario)
        self._anonimizar(usuario)
        return claves

    def marcar_archivos_eliminados(self, archivos: list[ArchivoAdjunto]) -> list[str]:
        ahora = ahora_utc()
        for archivo in archivos:
            archivo.estado = EstadoArchivo.ELIMINADO
            archivo.id_mensaje = None
            archivo.id_actividad = None
            archivo.nombre_original = NOMBRE_ARCHIVO_ELIMINADO
            archivo.fecha_expiracion = ahora
        return [a.clave_almacen for a in archivos]

    def _borrar_estudio(self, id_usuario: uuid.UUID) -> None:
        for conversacion in self._conversaciones.listar_todas_por_usuario(id_usuario):
            self._conversaciones.eliminar(conversacion)
        for evento in self._eventos.listar_por_usuario(id_usuario):
            self._eventos.eliminar(evento)
        for sesion in self._sesiones.listar_por_usuario(id_usuario):
            self._sesiones.eliminar(sesion)
        perfil = self._perfiles.obtener_por_usuario(id_usuario)
        if perfil is not None:
            self._perfiles.eliminar(perfil)

    def _desvincular_evidencia(self, id_usuario: uuid.UUID) -> None:
        for alerta in self._alertas.listar_por_usuario(id_usuario):
            alerta.detalle = None
        for consentimiento in self._consentimientos.listar_por_usuario(id_usuario):
            consentimiento.id_usuario = None

    @staticmethod
    def _anonimizar(usuario: Usuario) -> None:
        aleatorio = secrets.token_hex(16)
        usuario.nombre = NOMBRE_ANONIMO
        usuario.correo = f"{aleatorio}@{DOMINIO_ANONIMO}"
        usuario.correo_hash = sha256_hex(aleatorio)
        usuario.fecha_nacimiento = FECHA_NACIMIENTO_NEUTRA
        usuario.hash_contrasena = HASH_INUTILIZABLE
        usuario.activo = False
        usuario.version_token += 1
