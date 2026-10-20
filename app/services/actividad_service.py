import uuid

from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import DatoInvalidoError, RecursoNoEncontradoError
from app.models.actividad import Actividad
from app.models.archivo_adjunto import ArchivoAdjunto
from app.models.enums import EstadoActividad, EstadoArchivo, EstadoPlan, TipoEvento
from app.models.evento_aprendizaje import EventoAprendizaje
from app.repositories.archivo import ArchivoRepository
from app.repositories.conversacion import EventoAprendizajeRepository
from app.repositories.plan import ActividadRepository
from app.schemas.actividad import ActividadPublica, ActualizarActividadEntrada
from app.services.aprendizaje.perfil_aprendizaje_service import PerfilAprendizajeService
from app.services.archivo_service import ArchivoService
from app.services.presentacion import actividad_publica
from app.validators.propiedad import validar_recurso_propio
from app.validators.texto import normalizar_texto

ESTADOS_TERMINADOS = {EstadoActividad.COMPLETADA, EstadoActividad.OMITIDA}


class ActividadService:
    def __init__(
        self,
        actividades: ActividadRepository,
        archivos_repo: ArchivoRepository,
        eventos: EventoAprendizajeRepository,
        archivos: ArchivoService,
        perfiles: PerfilAprendizajeService,
        max_archivos_por_actividad: int,
        uow: UnitOfWork,
    ) -> None:
        self._actividades = actividades
        self._archivos_repo = archivos_repo
        self._eventos = eventos
        self._archivos = archivos
        self._perfiles = perfiles
        self._max_archivos = max_archivos_por_actividad
        self._uow = uow

    def actualizar(
        self, id_usuario: uuid.UUID, id_actividad: uuid.UUID, entrada: ActualizarActividadEntrada
    ) -> ActividadPublica:
        actividad = self._propia(id_usuario, id_actividad)
        self._aplicar_estado(actividad, entrada)
        if entrada.id_archivo is not None:
            self._adjuntar_archivo(id_usuario, actividad, entrada.id_archivo)
        self._actualizar_estado_plan(actividad)
        self._uow.commit()
        return actividad_publica(actividad, self._archivo_de(actividad))

    def _propia(self, id_usuario: uuid.UUID, id_actividad: uuid.UUID) -> Actividad:
        actividad = self._actividades.obtener_con_plan(id_actividad)
        if actividad is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(actividad.plan.id_usuario, id_usuario)
        return actividad

    def _aplicar_estado(self, actividad: Actividad, entrada: ActualizarActividadEntrada) -> None:
        completada_ahora = (
            entrada.estado == EstadoActividad.COMPLETADA
            and actividad.estado != EstadoActividad.COMPLETADA
        )
        actividad.estado = entrada.estado
        if entrada.respuesta_usuario is not None:
            actividad.respuesta_usuario = normalizar_texto(entrada.respuesta_usuario) or None
        actividad.fecha_completado = (
            ahora_utc() if entrada.estado == EstadoActividad.COMPLETADA else None
        )
        if completada_ahora:
            self._registrar_evento(actividad.plan.id_usuario)

    def _registrar_evento(self, id_usuario: uuid.UUID) -> None:
        if not self._perfiles.obtener_o_crear(id_usuario).personalizacion_activa:
            return
        self._eventos.agregar(
            EventoAprendizaje(
                id_usuario=id_usuario, tipo=TipoEvento.ACTIVIDAD_COMPLETADA, fecha=ahora_utc()
            )
        )

    def _adjuntar_archivo(
        self, id_usuario: uuid.UUID, actividad: Actividad, id_archivo: uuid.UUID
    ) -> None:
        if len(self._adjuntos(actividad)) >= self._max_archivos:
            raise DatoInvalidoError("Esta actividad ya tiene un archivo entregado.")
        archivo = self._archivos.obtener_para_adjuntar(
            id_usuario, id_archivo, actividad.id_actividad, actividad.plan.nivel_bloom
        )
        self._archivos.adjuntar(archivo, id_actividad=actividad.id_actividad)

    def _adjuntos(self, actividad: Actividad) -> list[ArchivoAdjunto]:
        return [
            a
            for a in self._archivos_repo.listar_por_actividades([actividad.id_actividad])
            if a.estado == EstadoArchivo.ADJUNTO
        ]

    @staticmethod
    def _actualizar_estado_plan(actividad: Actividad) -> None:
        plan = actividad.plan
        terminadas = all(a.estado in ESTADOS_TERMINADOS for a in plan.actividades)
        plan.estado = EstadoPlan.COMPLETADO if terminadas else EstadoPlan.EN_PROGRESO

    def _archivo_de(self, actividad: Actividad) -> ArchivoAdjunto | None:
        adjuntos = self._adjuntos(actividad)
        return adjuntos[0] if adjuntos else None
