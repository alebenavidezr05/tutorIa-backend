import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.tareas import TareasSegundoPlano
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import (
    ConversacionCerradaError,
    LLMNoDisponibleError,
    LLMRespuestaInvalidaError,
    RecursoNoEncontradoError,
)
from app.llm.base import (
    BloqueLLM,
    BloqueResultadoHerramienta,
    BloqueUsoHerramienta,
    LLMClient,
    LLMRespuesta,
    LLMSolicitud,
    MensajeLLM,
    TareaLLM,
)
from app.llm.herramientas import RESPONDER, herramientas_tutor
from app.llm.parser import LLMResponseParser
from app.llm.prompts_tutor import TutorPromptBuilder
from app.llm.selector_modelo import SelectorModelo, SenalesComplejidad
from app.models.conversacion import Conversacion
from app.models.enums import (
    AccionModeracion,
    AmbitoMensaje,
    CampoUso,
    CategoriaAlerta,
    EstadoConversacion,
    FormatoExplicacion,
    IntencionMensaje,
    OperacionIA,
    RolMensaje,
    TipoEvento,
)
from app.models.evento_aprendizaje import EventoAprendizaje
from app.models.mensaje import Mensaje
from app.models.perfil_aprendizaje import PerfilAprendizaje
from app.models.trabajo_visual import TrabajoVisual
from app.repositories.conversacion import (
    ConversacionRepository,
    EventoAprendizajeRepository,
    MensajeRepository,
    PerfilAprendizajeRepository,
)
from app.repositories.diagnostico import SesionDiagnosticoRepository
from app.repositories.fuente import FuenteRepository
from app.repositories.plan import PlanEstudioRepository
from app.repositories.usuario import UsuarioRepository
from app.repositories.video import VideoCuradoRepository
from app.schemas.bloques import (
    BloquePreguntaComprension,
    BloquePreguntaResumen,
    BloqueTexto,
    BloqueTutor,
    BloqueVideo,
    RespuestaTutor,
)
from app.schemas.conversacion import EnviarMensajeEntrada, MensajeTutorPublico
from app.services.aprendizaje.perfil_aprendizaje_service import PerfilAprendizajeService
from app.services.aprendizaje.senales_extractor import SenalesExtractor, SenalesMensaje
from app.services.archivo_service import ArchivoPreparado, ArchivoService
from app.services.consumo_service import ConsumoService
from app.services.estudiante import perfil_estudiante
from app.services.fuentes.fuentes_service import ContextoFuentes, FuentesService
from app.services.seguridad.alerta_seguridad_service import AlertaSeguridadService
from app.services.seguridad.moderacion_service import DecisionModeracion, ModeracionService
from app.services.seguridad.textos import (
    MENSAJE_NO_ACADEMICO,
    MENSAJE_RECHAZO,
    RESPALDO_PREGUNTA,
    RESPALDO_TEXTO,
    mensaje_apoyo,
)
from app.services.tutor.contexto_estudiante_builder import ContextoEstudianteBuilder, DatosContexto
from app.services.tutor.ejecutor_herramientas import EjecutorHerramientas
from app.services.tutor.estado_turno import EstadoTurno
from app.services.tutor.formatos import contenido_plano, formatos_usados, fuentes_citadas
from app.services.uso_service import UsoService
from app.services.videos.video_service import VideoService
from app.services.visual.trabajo_visual_service import TrabajoVisualService
from app.validators.mensaje import validar_mensaje_chat
from app.validators.privacidad import redactar_datos_personales
from app.validators.propiedad import validar_recurso_propio
from app.validators.respuesta_tutor import RespuestaTutorValidator

MS_POR_SEGUNDO = 1000
TURNOS_RECIENTES_NO_ENTENDI = 3
DETALLE_RIESGO_MODELO = "El modelo clasificó el mensaje como de riesgo."
TIPOS_CON_VIDEO = (BloqueVideo, BloquePreguntaResumen)


@dataclass(frozen=True)
class TurnoPreparado:
    conversacion: Conversacion
    texto: str
    senales: SenalesMensaje
    perfil: PerfilAprendizaje | None
    formatos_previos: list[FormatoExplicacion]
    archivo: ArchivoPreparado | None
    solicitud_base: LLMSolicitud
    estado: EstadoTurno


@dataclass(frozen=True)
class ResultadoTurno:
    respuesta: RespuestaTutor
    validado: bool


def _sin_videos_ajenos(respuesta: RespuestaTutor, ids_videos: set[uuid.UUID]) -> RespuestaTutor:
    bloques = [
        b
        for b in respuesta.bloques
        if not isinstance(b, TIPOS_CON_VIDEO) or b.id_video in ids_videos
    ]
    return respuesta.model_copy(update={"bloques": bloques})


def _respuesta_fija(ambito: AmbitoMensaje, texto: str) -> RespuestaTutor:
    return RespuestaTutor(ambito=ambito, bloques=[BloqueTexto(tipo="texto", contenido=texto)])


def respuesta_respaldo() -> RespuestaTutor:
    """Texto guiado sin afirmar hechos y una pregunta de comprensión genérica."""
    return RespuestaTutor(
        ambito=AmbitoMensaje.ACADEMICO,
        bloques=[
            BloqueTexto(tipo="texto", contenido=RESPALDO_TEXTO),
            BloquePreguntaComprension(tipo="pregunta_comprension", enunciado=RESPALDO_PREGUNTA),
        ],
    )


class TutorService:
    """Orquesta un turno: validar → moderar → contexto → bucle de herramientas → validar → persistir."""

    def __init__(
        self,
        conversaciones: ConversacionRepository,
        mensajes: MensajeRepository,
        eventos: EventoAprendizajeRepository,
        perfiles_repo: PerfilAprendizajeRepository,
        usuarios: UsuarioRepository,
        sesiones: SesionDiagnosticoRepository,
        planes: PlanEstudioRepository,
        fuentes_repo: FuenteRepository,
        videos_repo: VideoCuradoRepository,
        llm: LLMClient,
        prompts: TutorPromptBuilder,
        parser: LLMResponseParser,
        validador: RespuestaTutorValidator,
        selector: SelectorModelo,
        extractor: SenalesExtractor,
        contexto: ContextoEstudianteBuilder,
        ejecutor: EjecutorHerramientas,
        fuentes: FuentesService,
        videos: VideoService,
        perfiles: PerfilAprendizajeService,
        archivos: ArchivoService,
        moderacion: ModeracionService,
        alertas: AlertaSeguridadService,
        trabajos: TrabajoVisualService,
        uso: UsoService,
        consumo: ConsumoService,
        procesar_visual: Callable[[uuid.UUID], None],
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._conversaciones = conversaciones
        self._mensajes = mensajes
        self._eventos = eventos
        self._perfiles_repo = perfiles_repo
        self._usuarios = usuarios
        self._sesiones = sesiones
        self._planes = planes
        self._fuentes_repo = fuentes_repo
        self._videos_repo = videos_repo
        self._llm = llm
        self._prompts = prompts
        self._parser = parser
        self._validador = validador
        self._selector = selector
        self._extractor = extractor
        self._contexto = contexto
        self._ejecutor = ejecutor
        self._fuentes = fuentes
        self._videos = videos
        self._perfiles = perfiles
        self._archivos = archivos
        self._moderacion = moderacion
        self._alertas = alertas
        self._trabajos = trabajos
        self._uso = uso
        self._consumo = consumo
        self._procesar_visual = procesar_visual
        self._settings = settings
        self._uow = uow

    def responder(
        self,
        id_usuario: uuid.UUID,
        id_conversacion: uuid.UUID,
        entrada: EnviarMensajeEntrada,
        tareas: TareasSegundoPlano,
    ) -> MensajeTutorPublico:
        conversacion = self._conversacion_abierta(id_usuario, id_conversacion)
        texto = redactar_datos_personales(validar_mensaje_chat(entrada.contenido))
        self._uso.asegurar_disponible(id_usuario, CampoUso.MENSAJES)
        archivo = self._preparar_archivo(id_usuario, conversacion, entrada.id_archivo)
        decision = self._moderacion.evaluar_entrada(texto)
        if decision.accion != AccionModeracion.CONTINUAR:
            return self._responder_por_moderacion(conversacion, texto, decision)
        turno = self._preparar_turno(conversacion, texto, archivo)
        resultado = self._resolver_ambito(turno, self._ejecutar_bucle(turno))
        return self._persistir(turno, resultado, tareas)

    # Paso 1–4: conversación, archivo
    def _conversacion_abierta(
        self, id_usuario: uuid.UUID, id_conversacion: uuid.UUID
    ) -> Conversacion:
        conversacion = self._conversaciones.obtener_por_id(id_conversacion)
        if conversacion is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(conversacion.id_usuario, id_usuario)
        if conversacion.estado != EstadoConversacion.ABIERTA:
            raise ConversacionCerradaError()
        return conversacion

    def _preparar_archivo(
        self, id_usuario: uuid.UUID, conversacion: Conversacion, id_archivo: uuid.UUID | None
    ) -> ArchivoPreparado | None:
        if id_archivo is None:
            return None
        return self._archivos.preparar_para_llm(
            id_usuario, id_archivo, conversacion.id_conversacion, conversacion.nivel_cognitivo
        )

    # Paso 5: moderación (sin llamar al LLM)
    def _responder_por_moderacion(
        self, conversacion: Conversacion, texto: str, decision: DecisionModeracion
    ) -> MensajeTutorPublico:
        fijo = (
            mensaje_apoyo(self._settings.lineas_ayuda)
            if decision.accion == AccionModeracion.APOYO
            else MENSAJE_RECHAZO
        )
        respuesta = _respuesta_fija(AmbitoMensaje.RIESGO, fijo)
        self._uso.consumir(conversacion.id_usuario, CampoUso.MENSAJES)
        usuario_msg, tutor_msg = self._guardar_mensajes(
            conversacion, texto, None, respuesta, True, None
        )
        detalle = texto if decision.guardar_detalle else None
        self._alertas.registrar_automatica(
            conversacion.id_usuario,
            usuario_msg.id_mensaje,
            decision.categoria or CategoriaAlerta.OTRO,
            detalle,
        )
        conversacion.fecha_ultimo_mensaje = ahora_utc()
        self._uow.commit()
        return self._publico(tutor_msg, respuesta, [], None)

    # Paso 6–8: señales, contexto y modelo
    def _preparar_turno(
        self, conversacion: Conversacion, texto: str, archivo: ArchivoPreparado | None
    ) -> TurnoPreparado:
        historial = self._mensajes.listar_ultimos(
            conversacion.id_conversacion, self._settings.chat_ventana_mensajes
        )
        usuarios_previos = [m for m in historial if m.rol == RolMensaje.USUARIO]
        senales = self._extractor.extraer(
            texto, usuarios_previos[-1].contenido if usuarios_previos else None
        )
        perfil = self._perfil_activo(conversacion.id_usuario)
        estudiante = perfil_estudiante(self._usuario(conversacion.id_usuario), self._settings)
        estado = EstadoTurno(
            id_usuario=conversacion.id_usuario,
            contexto_fuentes=ContextoFuentes(conversacion.nivel_cognitivo, estudiante.tipo_nivel),
        )
        estado.fuentes.update(
            {
                f.id_fuente: f
                for f in self._fuentes_repo.listar_por_conversacion(conversacion.id_conversacion)
            }
        )
        contexto = self._contexto.construir(
            DatosContexto(
                conversacion=conversacion,
                estudiante=estudiante,
                preferencias=self._perfiles.preferencias(perfil) if perfil else None,
                sesion=self._sesiones.obtener_ultima_evaluada_por_usuario(conversacion.id_usuario),
                plan=self._planes.obtener_por_id(conversacion.id_plan)
                if conversacion.id_plan
                else None,
                video_activo=self._video_activo(historial),
                numero_turno=self._mensajes.contar_tutor(conversacion.id_conversacion) + 1,
                modo_guia=senales.intencion == IntencionMensaje.RESOLVER_TAREA,
            )
        )
        nivel = self._selector.elegir(
            SenalesComplejidad(
                texto,
                conversacion.nivel_cognitivo,
                self._no_entendi_recientes(usuarios_previos, senales),
                archivo is not None,
            )
        )
        solicitud = LLMSolicitud(
            tarea=TareaLLM.TUTOR,
            system=self._prompts.system(contexto),
            mensajes=(*self._historial_llm(historial), self._mensaje_nuevo(texto, archivo)),
            nivel_modelo=nivel,
            max_tokens=self._settings.llm_max_tokens_tutor,
            herramientas=herramientas_tutor(),
            herramienta_forzada="*",
        )
        previos = [m for m in historial if m.rol == RolMensaje.TUTOR]
        formatos_previos = (
            [FormatoExplicacion(f) for f in (previos[-1].formatos_usados or [])] if previos else []
        )
        return TurnoPreparado(
            conversacion, texto, senales, perfil, formatos_previos, archivo, solicitud, estado
        )

    def _perfil_activo(self, id_usuario: uuid.UUID) -> PerfilAprendizaje | None:
        perfil = self._perfiles_repo.obtener_por_usuario(id_usuario)
        return perfil if perfil is not None and perfil.personalizacion_activa else None

    def _usuario(self, id_usuario: uuid.UUID) -> Any:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        return usuario

    def _video_activo(self, historial: list[Mensaje]) -> Any:
        tutores = [m for m in historial if m.rol == RolMensaje.TUTOR]
        bloques = (tutores[-1].bloques or []) if tutores else []
        ids = [
            uuid.UUID(str(b["id_video"])) for b in bloques if b.get("tipo") == "pregunta_resumen"
        ]
        videos = self._videos_repo.obtener_por_ids(ids[:1])
        return videos[0] if videos else None

    def _no_entendi_recientes(
        self, usuarios_previos: list[Mensaje], senales: SenalesMensaje
    ) -> int:
        recientes = [
            self._extractor.extraer(m.contenido, None)
            for m in usuarios_previos[-(TURNOS_RECIENTES_NO_ENTENDI - 1) :]
        ]
        return sum(TipoEvento.NO_ENTENDIO in s.eventos for s in [*recientes, senales])

    @staticmethod
    def _historial_llm(historial: list[Mensaje]) -> list[MensajeLLM]:
        mensajes = [
            MensajeLLM.usuario(m.contenido)
            if m.rol == RolMensaje.USUARIO
            else MensajeLLM.asistente(m.contenido)
            for m in historial
        ]
        # La API exige que la conversación empiece con un mensaje del usuario.
        while mensajes and mensajes[0].rol == "assistant":
            mensajes.pop(0)
        return mensajes

    def _mensaje_nuevo(self, texto: str, archivo: ArchivoPreparado | None) -> MensajeLLM:
        bloques: tuple[BloqueLLM, ...] = archivo.bloques if archivo else ()
        return MensajeLLM(rol="user", contenido=(*bloques, self._prompts.mensaje_estudiante(texto)))

    # Paso 9–10: bucle de herramientas y validación (historial solo se agrega, nunca se edita)
    def _ejecutar_bucle(self, turno: TurnoPreparado) -> ResultadoTurno:
        mensajes = list(turno.solicitud_base.mensajes)
        reintentos = 0
        for _ in range(self._settings.chat_max_iteraciones_herramientas):
            respuesta = self._llamar(turno, mensajes)
            if respuesta.fue_rechazada:
                return ResultadoTurno(respuesta_respaldo(), validado=False)
            mensajes.append(MensajeLLM(rol="assistant", contenido=respuesta.bloques))
            usos = respuesta.usos_herramienta()
            final = next((u for u in usos if u.nombre == RESPONDER), None)
            if final is None:
                mensajes.append(self._continuacion(usos, turno.estado))
                continue
            candidata = self._validar(turno, final)
            if candidata.validado or candidata.respuesta.ambito != AmbitoMensaje.ACADEMICO:
                return candidata
            if reintentos >= self._settings.chat_max_reintentos:
                return ResultadoTurno(respuesta_respaldo(), validado=False)
            reintentos += 1
            mensajes.append(
                self._rechazo(final, usos, turno.estado, self._motivos(turno, candidata.respuesta))
            )
        raise LLMRespuestaInvalidaError()

    def _llamar(self, turno: TurnoPreparado, mensajes: list[MensajeLLM]) -> LLMRespuesta:
        if turno.estado.segundos_transcurridos() > self._settings.chat_timeout_turno_segundos:
            raise LLMNoDisponibleError("El tutor tardó demasiado. Intenta de nuevo.")
        solicitud = LLMSolicitud(
            tarea=turno.solicitud_base.tarea,
            system=turno.solicitud_base.system,
            mensajes=tuple(mensajes),
            nivel_modelo=turno.solicitud_base.nivel_modelo,
            max_tokens=turno.solicitud_base.max_tokens,
            herramientas=turno.solicitud_base.herramientas,
            herramienta_forzada=turno.solicitud_base.herramienta_forzada,
        )
        respuesta = self._llm.completar(solicitud)
        self._consumo.registrar_llm(turno.estado.id_usuario, OperacionIA.TUTOR, respuesta)
        turno.estado.respuestas.append(respuesta)
        return respuesta

    def _continuacion(self, usos: list[BloqueUsoHerramienta], estado: EstadoTurno) -> MensajeLLM:
        if not usos:
            return self._prompts.recordatorio_responder()
        return MensajeLLM(
            rol="user", contenido=tuple(self._ejecutor.ejecutar(u, estado) for u in usos)
        )

    def _validar(self, turno: TurnoPreparado, final: BloqueUsoHerramienta) -> ResultadoTurno:
        respuesta = _sin_videos_ajenos(
            self._parser.parse_respuesta_tutor(final.entrada), set(turno.estado.videos)
        )
        return ResultadoTurno(respuesta, validado=not self._motivos(turno, respuesta))

    def _motivos(self, turno: TurnoPreparado, respuesta: RespuestaTutor) -> tuple[str, ...]:
        resultado = self._validador.validar(
            respuesta,
            self._fuentes.autoridades(turno.estado.fuentes.values()),
            set(turno.estado.videos),
        )
        return resultado.motivos

    def _rechazo(
        self,
        final: BloqueUsoHerramienta,
        usos: list[BloqueUsoHerramienta],
        estado: EstadoTurno,
        motivos: tuple[str, ...],
    ) -> MensajeLLM:
        error = BloqueResultadoHerramienta(
            final.id, self._prompts.motivos_rechazo(motivos), es_error=True
        )
        otros = [self._ejecutor.ejecutar(u, estado) for u in usos if u.id != final.id]
        return MensajeLLM(rol="user", contenido=(*otros, error))

    def _resolver_ambito(self, turno: TurnoPreparado, resultado: ResultadoTurno) -> ResultadoTurno:
        ambito = resultado.respuesta.ambito
        if ambito == AmbitoMensaje.NO_ACADEMICO:
            return ResultadoTurno(_respuesta_fija(ambito, MENSAJE_NO_ACADEMICO), validado=True)
        if ambito == AmbitoMensaje.RIESGO:
            return ResultadoTurno(
                _respuesta_fija(ambito, mensaje_apoyo(self._settings.lineas_ayuda)), validado=True
            )
        return resultado

    # Paso 11–14: persistencia en una sola transacción, trabajo visual e hidratación
    def _persistir(
        self, turno: TurnoPreparado, resultado: ResultadoTurno, tareas: TareasSegundoPlano
    ) -> MensajeTutorPublico:
        conversacion, respuesta = turno.conversacion, resultado.respuesta
        self._consumir_cupos(turno)
        usuario_msg, tutor_msg = self._guardar_mensajes(
            conversacion, turno.texto, turno.senales, respuesta, resultado.validado, turno.estado
        )
        citadas = fuentes_citadas(respuesta.bloques) & set(turno.estado.fuentes)
        self._fuentes.vincular_a_mensaje(tutor_msg.id_mensaje, citadas)
        self._videos.persistir_pendientes()
        if turno.archivo is not None:
            self._archivos.adjuntar(turno.archivo.archivo, id_mensaje=usuario_msg.id_mensaje)
        trabajo = self._crear_trabajo(conversacion, tutor_msg, respuesta)
        self._registrar_aprendizaje(turno, usuario_msg)
        self._registrar_riesgo(turno, respuesta, usuario_msg)
        conversacion.fecha_ultimo_mensaje = ahora_utc()
        self._uow.commit()
        if trabajo is not None:
            id_trabajo = trabajo.id_trabajo
            tareas.programar(lambda: self._procesar_visual(id_trabajo))
        fuentes = [turno.estado.fuentes[i] for i in citadas]
        return self._publico(tutor_msg, respuesta, fuentes, trabajo)

    def _consumir_cupos(self, turno: TurnoPreparado) -> None:
        self._uso.consumir(turno.estado.id_usuario, CampoUso.MENSAJES)
        for _ in range(turno.estado.busquedas_video):
            self._uso.intentar_consumir(turno.estado.id_usuario, CampoUso.BUSQUEDAS_VIDEO)

    def _guardar_mensajes(
        self,
        conversacion: Conversacion,
        texto: str,
        senales: SenalesMensaje | None,
        respuesta: RespuestaTutor,
        validado: bool,
        estado: EstadoTurno | None,
    ) -> tuple[Mensaje, Mensaje]:
        orden = self._mensajes.siguiente_orden(conversacion.id_conversacion)
        ahora = ahora_utc()
        usuario_msg = self._mensajes.agregar(
            Mensaje(
                id_conversacion=conversacion.id_conversacion,
                orden=orden,
                rol=RolMensaje.USUARIO,
                contenido=texto,
                intencion=senales.intencion if senales else None,
                fecha=ahora,
            )
        )
        tokens_entrada, tokens_salida = estado.tokens() if estado else (None, None)
        tutor_msg = self._mensajes.agregar(
            Mensaje(
                id_conversacion=conversacion.id_conversacion,
                orden=orden + 1,
                rol=RolMensaje.TUTOR,
                contenido=contenido_plano(respuesta.bloques),
                bloques=[b.model_dump(mode="json") for b in respuesta.bloques],
                ambito=respuesta.ambito,
                formatos_usados=[f.value for f in self._formatos(respuesta)],
                validado=validado,
                modelo=estado.modelo() if estado else None,
                tokens_entrada=tokens_entrada,
                tokens_salida=tokens_salida,
                latencia_ms=int(estado.segundos_transcurridos() * MS_POR_SEGUNDO)
                if estado
                else None,
                fecha=ahora,
            )
        )
        return usuario_msg, tutor_msg

    @staticmethod
    def _formatos(respuesta: RespuestaTutor) -> list[FormatoExplicacion]:
        con_visual = (
            respuesta.ambito == AmbitoMensaje.ACADEMICO and respuesta.solicitud_visual is not None
        )
        return formatos_usados(respuesta.bloques, con_visual)

    def _crear_trabajo(
        self, conversacion: Conversacion, tutor_msg: Mensaje, respuesta: RespuestaTutor
    ) -> TrabajoVisual | None:
        if respuesta.ambito != AmbitoMensaje.ACADEMICO or respuesta.solicitud_visual is None:
            return None
        return self._trabajos.crear(
            tutor_msg.id_mensaje, conversacion.id_usuario, respuesta.solicitud_visual
        )

    def _registrar_aprendizaje(self, turno: TurnoPreparado, usuario_msg: Mensaje) -> None:
        if turno.perfil is None:
            return
        self._eventos.agregar_varios(
            EventoAprendizaje(
                id_usuario=turno.conversacion.id_usuario,
                id_conversacion=turno.conversacion.id_conversacion,
                id_mensaje=usuario_msg.id_mensaje,
                tipo=evento,
                fecha=ahora_utc(),
            )
            for evento in turno.senales.eventos
        )
        self._perfiles.registrar_turno(turno.perfil, turno.senales, turno.formatos_previos)

    def _registrar_riesgo(
        self, turno: TurnoPreparado, respuesta: RespuestaTutor, usuario_msg: Mensaje
    ) -> None:
        if respuesta.ambito != AmbitoMensaje.RIESGO:
            return
        self._alertas.registrar_automatica(
            turno.conversacion.id_usuario,
            usuario_msg.id_mensaje,
            CategoriaAlerta.OTRO,
            DETALLE_RIESGO_MODELO,
        )

    def _publico(
        self,
        tutor_msg: Mensaje,
        respuesta: RespuestaTutor,
        fuentes: list[Any],
        trabajo: TrabajoVisual | None,
    ) -> MensajeTutorPublico:
        bloques: list[BloqueTutor] = list(respuesta.bloques)
        return MensajeTutorPublico(
            id_mensaje=tutor_msg.id_mensaje,
            ambito=respuesta.ambito,
            bloques=self._videos.hidratar([b.model_dump(mode="json") for b in bloques]),
            fuentes=self._fuentes.publicas(fuentes),
            visual=self._trabajos.vista(trabajo) if trabajo else None,
            formatos_usados=tutor_msg.formatos_usados or [],
            validado=bool(tutor_msg.validado),
            fecha=tutor_msg.fecha,
        )
