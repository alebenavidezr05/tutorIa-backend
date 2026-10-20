"""Raíz de composición: construye repositorios y services para una sesión de base de datos."""

from functools import cached_property

from sqlalchemy.orm import Session

from app.core.contenedor import Contenedor
from app.core.unit_of_work import FabricaUnitOfWork, UnitOfWork
from app.llm.parser import LLMResponseParser
from app.llm.prompts import PromptBuilder
from app.llm.prompts_tutor import ConsolidacionPromptBuilder, TutorPromptBuilder
from app.llm.selector_modelo import SelectorModelo
from app.repositories.archivo import ArchivoRepository
from app.repositories.autorizacion import AutorizacionRepository
from app.repositories.conversacion import (
    ConversacionRepository,
    EventoAprendizajeRepository,
    MensajeRepository,
    PerfilAprendizajeRepository,
)
from app.repositories.diagnostico import SesionDiagnosticoRepository
from app.repositories.fuente import FuenteRepository
from app.repositories.plan import ActividadRepository, PlanEstudioRepository
from app.repositories.salud import SaludRepository
from app.repositories.seguridad import (
    AlertaSeguridadRepository,
    ConsentimientoRepository,
    SolicitudTitularRepository,
)
from app.repositories.suscripcion import EventoPagoRepository, SuscripcionRepository
from app.repositories.uso import (
    ConsumoIARepository,
    LimiteFrecuenciaRepository,
    UsoDiarioRepository,
)
from app.repositories.usuario import UsuarioRepository
from app.repositories.video import VideoCuradoRepository
from app.repositories.visual import RecursoVisualRepository, TrabajoVisualRepository
from app.services.actividad_service import ActividadService
from app.services.aprendizaje.actualizador_preferencias import ActualizadorPreferencias
from app.services.aprendizaje.perfil_aprendizaje_service import PerfilAprendizajeService
from app.services.aprendizaje.senales_extractor import SenalesExtractor
from app.services.archivo_service import ArchivoService
from app.services.auth_service import AuthService
from app.services.autorizacion_service import AutorizacionService
from app.services.consentimiento_service import ConsentimientoService
from app.services.consumo_service import ConsumoService
from app.services.diagnostico_service import DiagnosticoService
from app.services.evaluacion_service import EvaluacionService
from app.services.fuentes.fuentes_service import FuentesService
from app.services.fuentes.referencias_service import ReferenciasService
from app.services.historial_service import HistorialService
from app.services.limitador_service import LimitadorFrecuencia
from app.services.pago_service import PagoService
from app.services.perfil_service import PerfilService
from app.services.plan_service import PlanService
from app.services.politica_service import PoliticaService
from app.services.privacidad_service import PrivacidadService
from app.services.reporte_progreso_service import ReporteProgresoService
from app.services.retencion_service import RetencionService
from app.services.salud_service import SaludService
from app.services.seguridad.alerta_seguridad_service import AlertaSeguridadService
from app.services.seguridad.moderacion_service import ModeracionService
from app.services.supresor_datos import SupresorDatos
from app.services.suscripcion_service import SuscripcionService
from app.services.token_service import TokenService
from app.services.tutor.consolidacion_service import ConsolidacionService
from app.services.tutor.contexto_estudiante_builder import ContextoEstudianteBuilder
from app.services.tutor.conversacion_service import ConversacionService
from app.services.tutor.ejecutor_herramientas import EjecutorHerramientas
from app.services.tutor.feedback_service import FeedbackService
from app.services.tutor.tutor_service import TutorService
from app.services.uso_service import UsoService
from app.services.videos.video_service import VideoService
from app.services.visual.recurso_visual_service import RecursoVisualService
from app.services.visual.trabajo_visual_service import TrabajoVisualService
from app.validators.cuestionario import CuestionarioValidator
from app.validators.plan import PlanValidator
from app.validators.respuesta_tutor import RespuestaTutorValidator


def ejecutar_trabajo_visual(contenedor: Contenedor, id_trabajo: object) -> None:
    """Tarea en segundo plano: abre su propia sesión y unidad de trabajo, después del commit."""
    with contenedor.fabrica_sesiones() as session:
        FabricaServicios(contenedor, session).trabajo_visual.procesar(id_trabajo)  # type: ignore[arg-type]


class FabricaServicios:
    def __init__(self, contenedor: Contenedor, session: Session) -> None:
        self._c = contenedor
        self._s = session
        self.settings = contenedor.settings

    @property
    def contenedor(self) -> Contenedor:
        return self._c

    # Infraestructura
    @cached_property
    def uow(self) -> UnitOfWork:
        return UnitOfWork(self._s)

    @cached_property
    def fabrica_uow(self) -> FabricaUnitOfWork:
        return FabricaUnitOfWork(self._c.fabrica_sesiones)

    @cached_property
    def parser(self) -> LLMResponseParser:
        return LLMResponseParser()

    @cached_property
    def selector(self) -> SelectorModelo:
        return SelectorModelo(
            self.settings.complejidad_umbral, self.settings.selector_palabras_largo
        )

    @cached_property
    def prompts_tutor(self) -> TutorPromptBuilder:
        return TutorPromptBuilder(self.settings.tutor_nombre)

    # Repositorios
    @cached_property
    def usuarios_repo(self) -> UsuarioRepository:
        return UsuarioRepository(self._s)

    @cached_property
    def autorizaciones_repo(self) -> AutorizacionRepository:
        return AutorizacionRepository(self._s)

    @cached_property
    def sesiones_repo(self) -> SesionDiagnosticoRepository:
        return SesionDiagnosticoRepository(self._s)

    @cached_property
    def planes_repo(self) -> PlanEstudioRepository:
        return PlanEstudioRepository(self._s)

    @cached_property
    def actividades_repo(self) -> ActividadRepository:
        return ActividadRepository(self._s)

    @cached_property
    def suscripciones_repo(self) -> SuscripcionRepository:
        return SuscripcionRepository(self._s)

    @cached_property
    def eventos_pago_repo(self) -> EventoPagoRepository:
        return EventoPagoRepository(self._s)

    @cached_property
    def uso_repo(self) -> UsoDiarioRepository:
        return UsoDiarioRepository(self._s)

    @cached_property
    def limites_repo(self) -> LimiteFrecuenciaRepository:
        return LimiteFrecuenciaRepository(self._s)

    @cached_property
    def conversaciones_repo(self) -> ConversacionRepository:
        return ConversacionRepository(self._s)

    @cached_property
    def mensajes_repo(self) -> MensajeRepository:
        return MensajeRepository(self._s)

    @cached_property
    def eventos_repo(self) -> EventoAprendizajeRepository:
        return EventoAprendizajeRepository(self._s)

    @cached_property
    def perfiles_repo(self) -> PerfilAprendizajeRepository:
        return PerfilAprendizajeRepository(self._s)

    @cached_property
    def fuentes_repo(self) -> FuenteRepository:
        return FuenteRepository(self._s)

    @cached_property
    def recursos_repo(self) -> RecursoVisualRepository:
        return RecursoVisualRepository(self._s)

    @cached_property
    def trabajos_repo(self) -> TrabajoVisualRepository:
        return TrabajoVisualRepository(self._s)

    @cached_property
    def videos_repo(self) -> VideoCuradoRepository:
        return VideoCuradoRepository(self._s)

    @cached_property
    def archivos_repo(self) -> ArchivoRepository:
        return ArchivoRepository(self._s)

    @cached_property
    def alertas_repo(self) -> AlertaSeguridadRepository:
        return AlertaSeguridadRepository(self._s)

    @cached_property
    def consentimientos_repo(self) -> ConsentimientoRepository:
        return ConsentimientoRepository(self._s)

    @cached_property
    def solicitudes_repo(self) -> SolicitudTitularRepository:
        return SolicitudTitularRepository(self._s)

    # Services transversales
    @cached_property
    def tokens(self) -> TokenService:
        return TokenService(self._c.firmador, self.settings.jwt_expira_minutos)

    @cached_property
    def limitador(self) -> LimitadorFrecuencia:
        return LimitadorFrecuencia(
            self.limites_repo,
            self._c.indice,
            self.settings.rate_limit_login_intentos,
            self.settings.rate_limit_login_ventana_minutos,
        )

    @cached_property
    def politica(self) -> PoliticaService:
        return PoliticaService(self.settings, self._c.textos_legales)

    @cached_property
    def consentimientos(self) -> ConsentimientoService:
        return ConsentimientoService(
            self.consentimientos_repo,
            self.usuarios_repo,
            self.perfiles_repo,
            self.solicitudes_repo,
            self.politica,
            self._c.indice,
            self.settings,
            self.uow,
        )

    @cached_property
    def supresor(self) -> SupresorDatos:
        return SupresorDatos(
            self.conversaciones_repo,
            self.sesiones_repo,
            self.perfiles_repo,
            self.eventos_repo,
            self.archivos_repo,
            self.alertas_repo,
            self.consentimientos_repo,
        )

    @cached_property
    def uso(self) -> UsoService:
        return UsoService(self.uso_repo, self.suscripciones_repo, self.settings)

    @cached_property
    def suscripcion(self) -> SuscripcionService:
        return SuscripcionService(self.suscripciones_repo, self.uso)

    @cached_property
    def consumo(self) -> ConsumoService:
        return ConsumoService(self.fabrica_uow, self.settings)

    @cached_property
    def moderacion(self) -> ModeracionService:
        return ModeracionService(self._c.moderador, self.settings)

    @cached_property
    def alertas(self) -> AlertaSeguridadService:
        return AlertaSeguridadService(
            self.alertas_repo, self.mensajes_repo, self.conversaciones_repo, self.uow
        )

    @cached_property
    def fuentes(self) -> FuentesService:
        return FuentesService(self._c.fuentes, self.fuentes_repo, self.settings)

    @cached_property
    def referencias(self) -> ReferenciasService:
        return ReferenciasService(
            self.conversaciones_repo,
            self.mensajes_repo,
            self.fuentes_repo,
            self.trabajos_repo,
            self.recursos_repo,
            self.videos_repo,
        )

    @cached_property
    def videos(self) -> VideoService:
        return VideoService(self.videos_repo, self._c.videos, self.uso, self.settings)

    @cached_property
    def perfil_aprendizaje(self) -> PerfilAprendizajeService:
        return PerfilAprendizajeService(
            self.perfiles_repo,
            self.usuarios_repo,
            ActualizadorPreferencias(
                self.settings.perfil_alpha, self.settings.perfil_observaciones_confianza
            ),
            self.consentimientos,
            self.uow,
        )

    @cached_property
    def recursos(self) -> RecursoVisualService:
        return RecursoVisualService(
            self._c.imagenes,
            self._c.descargador,
            self._c.almacen,
            self.moderacion,
            self.recursos_repo,
            self.trabajos_repo,
            self.settings,
        )

    @cached_property
    def trabajo_visual(self) -> TrabajoVisualService:
        return TrabajoVisualService(
            self.trabajos_repo,
            self.mensajes_repo,
            self.usuarios_repo,
            self.recursos,
            self._c.imagenes_ia,
            self._c.procesador,
            self.moderacion,
            self.uso,
            self.consumo,
            self._c.indice,
            self.settings,
            self.uow,
        )

    @cached_property
    def archivos(self) -> ArchivoService:
        return ArchivoService(
            self.archivos_repo,
            self.conversaciones_repo,
            self.actividades_repo,
            self._c.almacen,
            self._c.procesador,
            self.moderacion,
            self.uso,
            self.supresor,
            self.settings,
            self.uow,
        )

    # Casos de uso
    @cached_property
    def autorizacion(self) -> AutorizacionService:
        return AutorizacionService(
            self.autorizaciones_repo,
            self.usuarios_repo,
            self.consentimientos,
            self.supresor,
            self._c.correo,
            self._c.almacen,
            self._c.indice,
            self.settings,
            self.uow,
        )

    @cached_property
    def auth(self) -> AuthService:
        return AuthService(
            self.usuarios_repo,
            self.suscripciones_repo,
            self.perfiles_repo,
            self._c.passwords,
            self.tokens,
            self.autorizacion,
            self.consentimientos,
            self.limitador,
            self._c.indice,
            self.settings,
            self.uow,
        )

    @cached_property
    def perfil(self) -> PerfilService:
        return PerfilService(
            self.usuarios_repo, self.supresor, self._c.almacen, self.settings, self.uow
        )

    @cached_property
    def diagnostico(self) -> DiagnosticoService:
        return DiagnosticoService(
            self.sesiones_repo,
            self.usuarios_repo,
            self.fuentes,
            self._c.llm,
            PromptBuilder(),
            self.parser,
            CuestionarioValidator(
                self.settings.diagnostico_preguntas_min, self.settings.diagnostico_preguntas_max
            ),
            self.selector,
            self.consumo,
            self.settings,
            self.uow,
        )

    @cached_property
    def evaluacion(self) -> EvaluacionService:
        return EvaluacionService(self.sesiones_repo, self.fuentes_repo, self.settings, self.uow)

    @cached_property
    def plan(self) -> PlanService:
        return PlanService(
            self.sesiones_repo,
            self.planes_repo,
            self.usuarios_repo,
            self.fuentes_repo,
            self.archivos_repo,
            self.fuentes,
            self._c.llm,
            PromptBuilder(),
            self.parser,
            PlanValidator(),
            self.selector,
            self.uso,
            self.consumo,
            self.settings,
            self.uow,
        )

    @cached_property
    def actividad(self) -> ActividadService:
        return ActividadService(
            self.actividades_repo,
            self.archivos_repo,
            self.eventos_repo,
            self.archivos,
            self.perfil_aprendizaje,
            self.settings.archivo_max_por_actividad,
            self.uow,
        )

    @cached_property
    def historial(self) -> HistorialService:
        return HistorialService(self.planes_repo, self.suscripcion, self.settings)

    @cached_property
    def reporte(self) -> ReporteProgresoService:
        return ReporteProgresoService(self.planes_repo, self.suscripcion)

    @cached_property
    def pagos(self) -> PagoService:
        return PagoService(
            self.suscripciones_repo,
            self.eventos_pago_repo,
            self.usuarios_repo,
            self.suscripcion,
            self.autorizacion,
            self._c.pasarela,
            self.settings,
            self.uow,
        )

    @cached_property
    def consolidacion(self) -> ConsolidacionService:
        return ConsolidacionService(
            self.conversaciones_repo,
            self.mensajes_repo,
            self.eventos_repo,
            self.perfiles_repo,
            self.perfil_aprendizaje,
            self._c.llm,
            ConsolidacionPromptBuilder(),
            self.parser,
            self.selector,
            self.consumo,
            self.referencias,
            self.settings,
            self.uow,
        )

    @cached_property
    def conversacion(self) -> ConversacionService:
        return ConversacionService(
            self.conversaciones_repo,
            self.mensajes_repo,
            self.planes_repo,
            self.sesiones_repo,
            self.fuentes_repo,
            self.archivos_repo,
            self.trabajos_repo,
            self.suscripcion,
            self.consolidacion,
            self.trabajo_visual,
            self.videos,
            self.supresor,
            self._c.almacen,
            self.settings,
            self.uow,
        )

    @cached_property
    def tutor(self) -> TutorService:
        contenedor = self._c
        return TutorService(
            self.conversaciones_repo,
            self.mensajes_repo,
            self.eventos_repo,
            self.perfiles_repo,
            self.usuarios_repo,
            self.sesiones_repo,
            self.planes_repo,
            self.fuentes_repo,
            self.videos_repo,
            self._c.llm,
            self.prompts_tutor,
            self.parser,
            RespuestaTutorValidator(),
            self.selector,
            SenalesExtractor(),
            ContextoEstudianteBuilder(self.settings.perfil_exploracion_cada),
            EjecutorHerramientas(
                self.fuentes, self.videos, self.parser, self.prompts_tutor, self.settings
            ),
            self.fuentes,
            self.videos,
            self.perfil_aprendizaje,
            self.archivos,
            self.moderacion,
            self.alertas,
            self.trabajo_visual,
            self.uso,
            self.consumo,
            lambda id_trabajo: ejecutar_trabajo_visual(contenedor, id_trabajo),
            self.settings,
            self.uow,
        )

    @cached_property
    def feedback(self) -> FeedbackService:
        return FeedbackService(
            self.mensajes_repo,
            self.eventos_repo,
            self.perfiles_repo,
            self.perfil_aprendizaje,
            self.uow,
        )

    @cached_property
    def privacidad(self) -> PrivacidadService:
        return PrivacidadService(
            self.usuarios_repo,
            self.perfiles_repo,
            self.planes_repo,
            self.conversaciones_repo,
            self.archivos_repo,
            self.solicitudes_repo,
            self.consentimientos,
            self.supresor,
            self._c.almacen,
            self._c.correo,
            self.settings,
            self.uow,
        )

    @cached_property
    def salud(self) -> SaludService:
        return SaludService(SaludRepository(self._s))

    @cached_property
    def retencion(self) -> RetencionService:
        return RetencionService(
            self.archivos_repo,
            self.conversaciones_repo,
            self.alertas_repo,
            ConsumoIARepository(self._s),
            self.recursos_repo,
            self.autorizaciones_repo,
            self.supresor,
            self._c.almacen,
            self.settings,
            self.uow,
        )
