import base64
import uuid
from dataclasses import dataclass
from datetime import timedelta

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.crypto.indice_ciego import sha256_hex
from app.exceptions.base import (
    ArchivoNoPermitidoError,
    DatoInvalidoError,
    RecursoNoEncontradoError,
)
from app.imagenes.base import ProcesadorImagenes
from app.llm.base import BloqueDocumentoLLM, BloqueImagenLLM, BloqueLLM, BloqueTextoLLM
from app.llm.politica_nivel import politica_de
from app.llm.prompts import envolver
from app.models.archivo_adjunto import ArchivoAdjunto
from app.models.enums import CampoUso, ContextoArchivo, EstadoArchivo, NivelCognitivo
from app.repositories.archivo import ArchivoRepository
from app.repositories.conversacion import ConversacionRepository
from app.repositories.plan import ActividadRepository
from app.schemas.archivo import ArchivoDescarga, ArchivoPublico, EntradaArchivo
from app.services.presentacion import archivo_publico
from app.services.seguridad.moderacion_service import ModeracionService
from app.services.supresor_datos import SupresorDatos
from app.services.uso_service import UsoService
from app.validators.archivo import MIME_TEXTO, validar_archivo, validar_texto_archivo
from app.validators.propiedad import validar_recurso_propio

MIME_PDF = "application/pdf"
PREFIJO_CLAVE = "archivos"
ETIQUETA_ARCHIVO = "archivo_estudiante"


@dataclass(frozen=True)
class ArchivoPreparado:
    archivo: ArchivoAdjunto
    bloques: tuple[BloqueLLM, ...]


class ArchivoService:
    """Archivos del nivel avanzado: tipo real por bytes, imágenes sin metadatos, moderados,
    guardados en el almacén privado y entregados solo a su propietario."""

    def __init__(
        self,
        archivos: ArchivoRepository,
        conversaciones: ConversacionRepository,
        actividades: ActividadRepository,
        almacen: Almacen,
        procesador: ProcesadorImagenes,
        moderacion: ModeracionService,
        uso: UsoService,
        supresor: SupresorDatos,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._archivos = archivos
        self._conversaciones = conversaciones
        self._actividades = actividades
        self._almacen = almacen
        self._procesador = procesador
        self._moderacion = moderacion
        self._uso = uso
        self._supresor = supresor
        self._settings = settings
        self._uow = uow

    def subir(
        self,
        id_usuario: uuid.UUID,
        entrada: EntradaArchivo,
        contexto: ContextoArchivo,
        id_contexto: uuid.UUID,
    ) -> ArchivoPublico:
        self._asegurar_nivel(self._nivel_del_contexto(id_usuario, contexto, id_contexto))
        self._uso.consumir(id_usuario, CampoUso.ARCHIVOS)
        mime, nombre = validar_archivo(
            entrada.nombre,
            entrada.contenido,
            self._settings.archivo_mimes_permitidos,
            self._settings.archivo_max_bytes,
        )
        contenido, mime = self._sanear(entrada.contenido, mime)
        clave = f"{PREFIJO_CLAVE}/{id_usuario}/{uuid.uuid4()}"
        self._almacen.guardar(clave, contenido, mime)
        archivo = self._archivos.agregar(
            self._nuevo(id_usuario, id_contexto, nombre, mime, contenido, clave)
        )
        self._uow.commit()
        return archivo_publico(archivo)

    def descargar(self, id_usuario: uuid.UUID, id_archivo: uuid.UUID) -> ArchivoDescarga:
        archivo = self._propio(id_usuario, id_archivo)
        return ArchivoDescarga(
            archivo.nombre_original, self._almacen.leer(archivo.clave_almacen), archivo.mime
        )

    def eliminar(self, id_usuario: uuid.UUID, id_archivo: uuid.UUID) -> None:
        claves = self._supresor.marcar_archivos_eliminados([self._propio(id_usuario, id_archivo)])
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(claves)

    def preparar_para_llm(
        self,
        id_usuario: uuid.UUID,
        id_archivo: uuid.UUID,
        id_contexto: uuid.UUID,
        nivel: NivelCognitivo,
    ) -> ArchivoPreparado:
        self._asegurar_nivel(nivel)
        archivo = self._propio(id_usuario, id_archivo)
        if archivo.estado != EstadoArchivo.SUBIDO or archivo.id_contexto != id_contexto:
            raise DatoInvalidoError("Ese archivo ya se entregó o pertenece a otro contexto.")
        return ArchivoPreparado(
            archivo, self._bloques(archivo, self._almacen.leer(archivo.clave_almacen))
        )

    def adjuntar(
        self,
        archivo: ArchivoAdjunto,
        id_mensaje: uuid.UUID | None = None,
        id_actividad: uuid.UUID | None = None,
    ) -> None:
        """No confirma: se adjunta dentro de la transacción del turno o de la actividad."""
        archivo.estado = EstadoArchivo.ADJUNTO
        archivo.id_mensaje = id_mensaje
        archivo.id_actividad = id_actividad
        archivo.fecha_expiracion = ahora_utc() + timedelta(
            days=self._settings.archivo_retencion_dias
        )

    def obtener_para_adjuntar(
        self,
        id_usuario: uuid.UUID,
        id_archivo: uuid.UUID,
        id_contexto: uuid.UUID,
        nivel: NivelCognitivo,
    ) -> ArchivoAdjunto:
        return self.preparar_para_llm(id_usuario, id_archivo, id_contexto, nivel).archivo

    def _nivel_del_contexto(
        self, id_usuario: uuid.UUID, contexto: ContextoArchivo, id_contexto: uuid.UUID
    ) -> NivelCognitivo:
        if contexto == ContextoArchivo.CONVERSACION:
            conversacion = self._conversaciones.obtener_por_id(id_contexto)
            if conversacion is None:
                raise RecursoNoEncontradoError()
            validar_recurso_propio(conversacion.id_usuario, id_usuario)
            return conversacion.nivel_cognitivo
        actividad = self._actividades.obtener_con_plan(id_contexto)
        if actividad is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(actividad.plan.id_usuario, id_usuario)
        return actividad.plan.nivel_bloom

    @staticmethod
    def _asegurar_nivel(nivel: NivelCognitivo) -> None:
        if not politica_de(nivel).permite_archivos:
            raise ArchivoNoPermitidoError()

    def _sanear(self, contenido: bytes, mime: str) -> tuple[bytes, str]:
        if mime == MIME_TEXTO:
            texto = validar_texto_archivo(contenido, self._settings.archivo_texto_max_caracteres)
            self._moderacion.evaluar_archivo(contenido, mime, texto)
            return contenido, mime
        if mime == MIME_PDF:
            # Un PDF no se puede moderar antes de enviarlo: queda a cargo de la capa del modelo.
            return contenido, mime
        imagen = self._procesador.recodificar(contenido, self._settings.archivo_imagen_lado_max)
        self._moderacion.evaluar_archivo(imagen.contenido, imagen.mime, None)
        return imagen.contenido, imagen.mime

    def _nuevo(
        self,
        id_usuario: uuid.UUID,
        id_contexto: uuid.UUID,
        nombre: str,
        mime: str,
        contenido: bytes,
        clave: str,
    ) -> ArchivoAdjunto:
        ahora = ahora_utc()
        return ArchivoAdjunto(
            id_usuario=id_usuario,
            id_contexto=id_contexto,
            nombre_original=nombre,
            mime=mime,
            tamano_bytes=len(contenido),
            sha256=sha256_hex(contenido),
            clave_almacen=clave,
            estado=EstadoArchivo.SUBIDO,
            fecha_creacion=ahora,
            fecha_expiracion=ahora + timedelta(hours=self._settings.archivo_subido_horas),
        )

    def _propio(self, id_usuario: uuid.UUID, id_archivo: uuid.UUID) -> ArchivoAdjunto:
        archivo = self._archivos.obtener_por_id(id_archivo)
        if archivo is None or archivo.estado == EstadoArchivo.ELIMINADO:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(archivo.id_usuario, id_usuario)
        return archivo

    @staticmethod
    def _bloques(archivo: ArchivoAdjunto, contenido: bytes) -> tuple[BloqueLLM, ...]:
        if archivo.mime == MIME_TEXTO:
            return (BloqueTextoLLM(envolver(ETIQUETA_ARCHIVO, contenido.decode("utf-8"))),)
        datos = base64.standard_b64encode(contenido).decode()
        if archivo.mime == MIME_PDF:
            return (BloqueDocumentoLLM(MIME_PDF, datos),)
        return (BloqueImagenLLM(archivo.mime, datos),)
