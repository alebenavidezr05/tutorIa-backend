"""Dependencias de FastAPI: sin lógica, solo conectan la petición con la raíz de composición."""

import uuid
from collections.abc import Callable, Iterator

from fastapi import BackgroundTasks, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.contenedor import Contenedor
from app.core.cookies import CookieSesion
from app.core.fabrica import FabricaServicios
from app.core.tareas import TareasFastAPI, TareasSegundoPlano
from app.models.enums import Capacidad
from app.schemas.archivo import EntradaArchivo
from app.schemas.auth import ContextoSolicitud
from app.services.actividad_service import ActividadService
from app.services.aprendizaje.perfil_aprendizaje_service import PerfilAprendizajeService
from app.services.archivo_service import ArchivoService
from app.services.auth_service import AuthService
from app.services.autorizacion_service import AutorizacionService
from app.services.consentimiento_service import ConsentimientoService
from app.services.diagnostico_service import DiagnosticoService
from app.services.evaluacion_service import EvaluacionService
from app.services.fuentes.referencias_service import ReferenciasService
from app.services.historial_service import HistorialService
from app.services.pago_service import PagoService
from app.services.perfil_service import PerfilService
from app.services.plan_service import PlanService
from app.services.politica_service import PoliticaService
from app.services.privacidad_service import PrivacidadService
from app.services.reporte_progreso_service import ReporteProgresoService
from app.services.salud_service import SaludService
from app.services.seguridad.alerta_seguridad_service import AlertaSeguridadService
from app.services.suscripcion_service import SuscripcionService
from app.services.tutor.consolidacion_service import ConsolidacionService
from app.services.tutor.conversacion_service import ConversacionService
from app.services.tutor.feedback_service import FeedbackService
from app.services.tutor.tutor_service import TutorService
from app.services.visual.recurso_visual_service import RecursoVisualService
from app.services.visual.trabajo_visual_service import TrabajoVisualService


def get_contenedor(request: Request) -> Contenedor:
    contenedor: Contenedor = request.app.state.contenedor
    return contenedor


def get_db(contenedor: Contenedor = Depends(get_contenedor)) -> Iterator[Session]:
    with contenedor.fabrica_sesiones() as session:
        yield session


def get_fabrica(
    contenedor: Contenedor = Depends(get_contenedor), session: Session = Depends(get_db)
) -> FabricaServicios:
    return FabricaServicios(contenedor, session)


def get_cookie_sesion(contenedor: Contenedor = Depends(get_contenedor)) -> CookieSesion:
    return CookieSesion(contenedor.settings)


def get_contexto(request: Request) -> ContextoSolicitud:
    return ContextoSolicitud(ip=request.client.host if request.client else None)


def get_tareas(background_tasks: BackgroundTasks) -> TareasSegundoPlano:
    return TareasFastAPI(background_tasks)


def get_auth_service(f: FabricaServicios = Depends(get_fabrica)) -> AuthService:
    return f.auth


def _token(request: Request, contenedor: Contenedor) -> str | None:
    return request.cookies.get(contenedor.settings.cookie_nombre)


def get_usuario_actual_id(
    request: Request,
    contenedor: Contenedor = Depends(get_contenedor),
    auth: AuthService = Depends(get_auth_service),
) -> uuid.UUID:
    """Acceso «Sesión»: cookie válida aunque la cuenta esté pendiente de autorización."""
    return auth.validar_sesion(_token(request, contenedor))


def get_usuario_activo_id(
    request: Request,
    contenedor: Contenedor = Depends(get_contenedor),
    auth: AuthService = Depends(get_auth_service),
) -> uuid.UUID:
    """Acceso «Activa»: sesión válida, cuenta activa, autorizada y con la política vigente."""
    return auth.asegurar_sesion_activa(_token(request, contenedor))


def get_autorizacion_service(f: FabricaServicios = Depends(get_fabrica)) -> AutorizacionService:
    return f.autorizacion


def get_perfil_service(f: FabricaServicios = Depends(get_fabrica)) -> PerfilService:
    return f.perfil


def get_suscripcion_service(f: FabricaServicios = Depends(get_fabrica)) -> SuscripcionService:
    return f.suscripcion


def get_pago_service(f: FabricaServicios = Depends(get_fabrica)) -> PagoService:
    return f.pagos


def get_reporte_service(f: FabricaServicios = Depends(get_fabrica)) -> ReporteProgresoService:
    return f.reporte


def get_diagnostico_service(f: FabricaServicios = Depends(get_fabrica)) -> DiagnosticoService:
    return f.diagnostico


def get_evaluacion_service(f: FabricaServicios = Depends(get_fabrica)) -> EvaluacionService:
    return f.evaluacion


def get_plan_service(f: FabricaServicios = Depends(get_fabrica)) -> PlanService:
    return f.plan


def get_actividad_service(f: FabricaServicios = Depends(get_fabrica)) -> ActividadService:
    return f.actividad


def get_archivo_service(f: FabricaServicios = Depends(get_fabrica)) -> ArchivoService:
    return f.archivos


def get_historial_service(f: FabricaServicios = Depends(get_fabrica)) -> HistorialService:
    return f.historial


def get_conversacion_service(f: FabricaServicios = Depends(get_fabrica)) -> ConversacionService:
    return f.conversacion


def get_tutor_service(f: FabricaServicios = Depends(get_fabrica)) -> TutorService:
    return f.tutor


def get_consolidacion_service(f: FabricaServicios = Depends(get_fabrica)) -> ConsolidacionService:
    return f.consolidacion


def get_referencias_service(f: FabricaServicios = Depends(get_fabrica)) -> ReferenciasService:
    return f.referencias


def get_feedback_service(f: FabricaServicios = Depends(get_fabrica)) -> FeedbackService:
    return f.feedback


def get_alerta_service(f: FabricaServicios = Depends(get_fabrica)) -> AlertaSeguridadService:
    return f.alertas


def get_trabajo_visual_service(f: FabricaServicios = Depends(get_fabrica)) -> TrabajoVisualService:
    return f.trabajo_visual


def get_recurso_visual_service(f: FabricaServicios = Depends(get_fabrica)) -> RecursoVisualService:
    return f.recursos


def get_perfil_aprendizaje_service(
    f: FabricaServicios = Depends(get_fabrica),
) -> PerfilAprendizajeService:
    return f.perfil_aprendizaje


def get_politica_service(f: FabricaServicios = Depends(get_fabrica)) -> PoliticaService:
    return f.politica


def get_consentimiento_service(f: FabricaServicios = Depends(get_fabrica)) -> ConsentimientoService:
    return f.consentimientos


def get_privacidad_service(f: FabricaServicios = Depends(get_fabrica)) -> PrivacidadService:
    return f.privacidad


def get_salud_service(f: FabricaServicios = Depends(get_fabrica)) -> SaludService:
    return f.salud


def get_salud_sin_db() -> SaludService:
    return SaludService()


def requiere(capacidad: Capacidad) -> Callable[..., None]:
    """Dependencia de función de pago: el servidor decide, el cliente solo muestra u oculta."""

    def _asegurar(
        id_usuario: uuid.UUID = Depends(get_usuario_activo_id),
        suscripciones: SuscripcionService = Depends(get_suscripcion_service),
    ) -> None:
        suscripciones.asegurar_capacidad(id_usuario, capacidad)

    return _asegurar


requiere_reporte_progreso = requiere(Capacidad.REPORTE_PROGRESO)


async def get_cuerpo_crudo(request: Request) -> bytes:
    return await request.body()


def get_cabeceras(request: Request) -> dict[str, str]:
    return dict(request.headers)


def get_entrada_archivo(
    archivo: UploadFile = File(...), contenedor: Contenedor = Depends(get_contenedor)
) -> EntradaArchivo:
    # Se lee un byte más que el máximo: basta para detectar el exceso sin cargar archivos enormes.
    contenido = archivo.file.read(contenedor.settings.archivo_max_bytes + 1)
    return EntradaArchivo(nombre=archivo.filename or "archivo", contenido=contenido)
