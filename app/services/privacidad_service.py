import json
import uuid
from datetime import date
from typing import Any

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.correo import plantillas
from app.correo.base import CorreoClient
from app.exceptions.base import RecursoNoEncontradoError
from app.models.enums import EstadoSolicitud, TipoSolicitud
from app.models.solicitud_titular import SolicitudTitular
from app.models.usuario import Usuario
from app.repositories.archivo import ArchivoRepository
from app.repositories.conversacion import ConversacionRepository, PerfilAprendizajeRepository
from app.repositories.plan import PlanEstudioRepository
from app.repositories.seguridad import SolicitudTitularRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.archivo import ArchivoDescarga
from app.schemas.privacidad import MisDatos, SolicitudEntrada, SolicitudPublica
from app.services.consentimiento_service import ConsentimientoService
from app.services.plazos import fecha_limite_solicitud
from app.services.supresor_datos import SupresorDatos
from app.validators.texto import normalizar_texto

NOMBRE_EXPORTACION = "mis_datos_tutoria.json"
MIME_JSON = "application/json"


class PrivacidadService:
    """Derechos del titular (Ley 1581): conocer, exportar, solicitar y suprimir."""

    def __init__(
        self,
        usuarios: UsuarioRepository,
        perfiles: PerfilAprendizajeRepository,
        planes: PlanEstudioRepository,
        conversaciones: ConversacionRepository,
        archivos: ArchivoRepository,
        solicitudes: SolicitudTitularRepository,
        consentimientos: ConsentimientoService,
        supresor: SupresorDatos,
        almacen: Almacen,
        correo: CorreoClient,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._usuarios = usuarios
        self._perfiles = perfiles
        self._planes = planes
        self._conversaciones = conversaciones
        self._archivos = archivos
        self._solicitudes = solicitudes
        self._consentimientos = consentimientos
        self._supresor = supresor
        self._almacen = almacen
        self._correo = correo
        self._settings = settings
        self._uow = uow

    def mis_datos(self, id_usuario: uuid.UUID) -> MisDatos:
        usuario = self._usuario(id_usuario)
        perfil = self._perfiles.obtener_por_usuario(id_usuario)
        return MisDatos(
            usuario=self._datos_usuario(usuario),
            perfil_aprendizaje={
                "personalizacion_activa": perfil.personalizacion_activa,
                "preferencias": perfil.preferencias,
            }
            if perfil
            else {},
            planes=[
                {
                    "titulo": p.titulo,
                    "tema": p.sesion.tema,
                    "nivel": p.nivel_bloom.value,
                    "fecha": p.fecha_generacion.isoformat(),
                }
                for p in self._planes.listar_por_usuario(id_usuario)
            ],
            conversaciones=[
                {
                    "tema": c.tema,
                    "estado": c.estado.value,
                    "inicio": c.fecha_inicio.isoformat(),
                    "resumen": c.resumen,
                }
                for c in self._conversaciones.listar_todas_por_usuario(id_usuario)
            ],
            archivos=[
                {
                    "nombre": a.nombre_original,
                    "tipo": a.mime,
                    "tamano_bytes": a.tamano_bytes,
                    "fecha": a.fecha_creacion.isoformat(),
                }
                for a in self._archivos.listar_por_usuario(id_usuario)
            ],
            consentimientos=self._consentimientos.estado_actual(id_usuario),
            solicitudes=self.listar_solicitudes(id_usuario),
        )

    def exportar(self, id_usuario: uuid.UUID) -> ArchivoDescarga:
        contenido = json.dumps(
            self.mis_datos(id_usuario).model_dump(mode="json"), ensure_ascii=False, indent=2
        )
        return ArchivoDescarga(NOMBRE_EXPORTACION, contenido.encode("utf-8"), MIME_JSON)

    def crear_solicitud(self, id_usuario: uuid.UUID, entrada: SolicitudEntrada) -> SolicitudPublica:
        usuario = self._usuario(id_usuario)
        ahora = ahora_utc()
        solicitud = self._solicitudes.crear(
            SolicitudTitular(
                id_usuario=id_usuario,
                tipo=entrada.tipo,
                detalle=normalizar_texto(entrada.detalle),
                estado=EstadoSolicitud.RECIBIDA,
                fecha_recepcion=ahora,
                fecha_limite=fecha_limite_solicitud(entrada.tipo, ahora.date(), self._settings),
            )
        )
        self._uow.commit()
        self._correo.enviar(
            plantillas.solicitud_titular_recibida(
                usuario.correo, entrada.tipo.value, solicitud.fecha_limite.isoformat()
            )
        )
        return self._publica(solicitud)

    def listar_solicitudes(self, id_usuario: uuid.UUID) -> list[SolicitudPublica]:
        return [self._publica(s) for s in self._solicitudes.listar_por_usuario(id_usuario)]

    def resolver(
        self, id_solicitud: uuid.UUID, estado: EstadoSolicitud, respuesta: str
    ) -> SolicitudPublica:
        """Uso administrativo: una persona responde la solicitud; la supresión se ejecuta aquí."""
        solicitud = self._solicitudes.obtener_por_id(id_solicitud)
        if solicitud is None:
            raise RecursoNoEncontradoError()
        solicitud.estado = estado
        solicitud.respuesta = normalizar_texto(respuesta)
        solicitud.fecha_respuesta = ahora_utc()
        claves = self._suprimir_si_corresponde(solicitud, estado)
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(claves)
        return self._publica(solicitud)

    def suprimir(self, id_usuario: uuid.UUID) -> None:
        claves = self._supresor.suprimir(self._usuario(id_usuario))
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(claves)

    def listar_por_vencer(self, hasta: date) -> list[SolicitudTitular]:
        return self._solicitudes.listar_por_vencer(hasta)

    def _suprimir_si_corresponde(
        self, solicitud: SolicitudTitular, estado: EstadoSolicitud
    ) -> list[str]:
        if (
            solicitud.tipo != TipoSolicitud.SUPRESION
            or estado != EstadoSolicitud.RESPONDIDA
            or solicitud.id_usuario is None
        ):
            return []
        return self._supresor.suprimir(self._usuario(solicitud.id_usuario))

    def _usuario(self, id_usuario: uuid.UUID) -> Usuario:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        return usuario

    @staticmethod
    def _datos_usuario(usuario: Usuario) -> dict[str, Any]:
        return {
            "nombre": usuario.nombre,
            "correo": usuario.correo,
            "fecha_nacimiento": usuario.fecha_nacimiento.isoformat(),
            "tipo_nivel": usuario.tipo_nivel.value,
            "nivel_educativo": usuario.nivel_educativo,
            "estado_cuenta": usuario.estado_cuenta.value,
            "fecha_registro": usuario.fecha_registro.isoformat(),
            "version_politica_aceptada": usuario.version_texto_tratamiento,
        }

    @staticmethod
    def _publica(solicitud: SolicitudTitular) -> SolicitudPublica:
        return SolicitudPublica(
            id_solicitud=solicitud.id_solicitud,
            tipo=solicitud.tipo,
            estado=solicitud.estado,
            fecha_limite=solicitud.fecha_limite,
        )
