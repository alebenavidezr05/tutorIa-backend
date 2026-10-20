import uuid
from datetime import timedelta

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import DatoInvalidoError, FuncionPremiumError, RecursoNoEncontradoError
from app.models.conversacion import Conversacion
from app.models.enums import Capacidad, EstadoConversacion, NivelCognitivo, RolMensaje
from app.models.mensaje import Mensaje
from app.repositories.archivo import ArchivoRepository
from app.repositories.conversacion import ConversacionRepository, MensajeRepository
from app.repositories.diagnostico import SesionDiagnosticoRepository
from app.repositories.fuente import FuenteRepository
from app.repositories.plan import PlanEstudioRepository
from app.repositories.visual import TrabajoVisualRepository
from app.schemas.conversacion import (
    ConversacionDetalle,
    ConversacionesPagina,
    ConversacionPublica,
    IniciarConversacionEntrada,
    MensajePublico,
)
from app.services.presentacion import archivo_publico, conversacion_publica, fuente_publica
from app.services.supresor_datos import SupresorDatos
from app.services.suscripcion_service import SuscripcionService
from app.services.tutor.consolidacion_service import ConsolidacionService
from app.services.videos.video_service import VideoService
from app.services.visual.trabajo_visual_service import TrabajoVisualService
from app.validators.perfil import normalizar_tema
from app.validators.propiedad import validar_recurso_propio

NIVEL_POR_DEFECTO = NivelCognitivo.BASICO


class ConversacionService:
    def __init__(
        self,
        conversaciones: ConversacionRepository,
        mensajes: MensajeRepository,
        planes: PlanEstudioRepository,
        sesiones: SesionDiagnosticoRepository,
        fuentes: FuenteRepository,
        archivos: ArchivoRepository,
        trabajos_repo: TrabajoVisualRepository,
        suscripciones: SuscripcionService,
        consolidacion: ConsolidacionService,
        trabajos: TrabajoVisualService,
        videos: VideoService,
        supresor: SupresorDatos,
        almacen: Almacen,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._conversaciones = conversaciones
        self._mensajes = mensajes
        self._planes = planes
        self._sesiones = sesiones
        self._fuentes = fuentes
        self._archivos = archivos
        self._trabajos_repo = trabajos_repo
        self._suscripciones = suscripciones
        self._consolidacion = consolidacion
        self._trabajos = trabajos
        self._videos = videos
        self._supresor = supresor
        self._almacen = almacen
        self._settings = settings
        self._uow = uow

    def iniciar(
        self, id_usuario: uuid.UUID, entrada: IniciarConversacionEntrada
    ) -> ConversacionPublica:
        self._consolidar_inactiva(id_usuario)
        tema, nivel = self._tema_y_nivel(id_usuario, entrada)
        existente = self._asegurar_temas_simultaneos(id_usuario, tema)
        if existente is not None:
            self._uow.commit()
            return conversacion_publica(existente)
        ahora = ahora_utc()
        conversacion = self._conversaciones.agregar(
            Conversacion(
                id_usuario=id_usuario,
                id_plan=entrada.id_plan,
                tema=tema,
                nivel_cognitivo=nivel,
                estado=EstadoConversacion.ABIERTA,
                consolidada=False,
                fecha_inicio=ahora,
                fecha_ultimo_mensaje=ahora,
            )
        )
        self._uow.commit()
        return conversacion_publica(conversacion)

    def listar(self, id_usuario: uuid.UUID, pagina: int, tamano: int) -> ConversacionesPagina:
        items = self._conversaciones.listar_por_usuario(id_usuario, (pagina - 1) * tamano, tamano)
        return ConversacionesPagina(
            items=[conversacion_publica(c) for c in items],
            total=self._conversaciones.contar_por_usuario(id_usuario),
            pagina=pagina,
            tamano=tamano,
        )

    def obtener(self, id_usuario: uuid.UUID, id_conversacion: uuid.UUID) -> ConversacionDetalle:
        conversacion = self._propia(id_usuario, id_conversacion)
        mensajes = self._mensajes.listar_por_conversacion(id_conversacion)
        publica = conversacion_publica(conversacion)
        return ConversacionDetalle(
            **publica.model_dump(), mensajes=self._mensajes_publicos(mensajes)
        )

    def eliminar(self, id_usuario: uuid.UUID, id_conversacion: uuid.UUID) -> None:
        conversacion = self._propia(id_usuario, id_conversacion)
        ids_mensajes = [
            m.id_mensaje for m in self._mensajes.listar_por_conversacion(id_conversacion)
        ]
        archivos = [
            *self._archivos.listar_por_mensajes(ids_mensajes),
            *self._archivos.listar_por_contexto(id_conversacion),
        ]
        claves = self._supresor.marcar_archivos_eliminados(
            list({a.id_archivo: a for a in archivos}.values())
        )
        self._conversaciones.eliminar(conversacion)
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(claves)

    def _consolidar_inactiva(self, id_usuario: uuid.UUID) -> None:
        limite = ahora_utc() - timedelta(minutes=self._settings.chat_inactividad_minutos)
        inactiva = self._conversaciones.obtener_abierta_inactiva(id_usuario, limite)
        if inactiva is not None:
            self._consolidacion.consolidar(inactiva)

    def _tema_y_nivel(
        self, id_usuario: uuid.UUID, entrada: IniciarConversacionEntrada
    ) -> tuple[str, NivelCognitivo]:
        if entrada.id_plan is not None:
            plan = self._planes.obtener_con_actividades(entrada.id_plan)
            if plan is None:
                raise RecursoNoEncontradoError()
            validar_recurso_propio(plan.id_usuario, id_usuario)
            return plan.sesion.tema, plan.nivel_bloom
        if not entrada.tema:
            raise DatoInvalidoError("Indica el tema de la conversación o el plan de estudio.")
        sesion = self._sesiones.obtener_ultima_evaluada_por_usuario(id_usuario)
        return entrada.tema, (
            sesion.nivel_estimado if sesion and sesion.nivel_estimado else NIVEL_POR_DEFECTO
        )

    def _asegurar_temas_simultaneos(self, id_usuario: uuid.UUID, tema: str) -> Conversacion | None:
        """Plan gratuito: una sola conversación abierta. Si es el mismo tema, se reutiliza."""
        if self._suscripciones.tiene_capacidad(id_usuario, Capacidad.TEMAS_SIMULTANEOS):
            return None
        abiertas = [
            c
            for c in self._conversaciones.listar_abiertas(id_usuario)
            if c.estado == EstadoConversacion.ABIERTA
        ]
        mismo_tema = next(
            (c for c in abiertas if normalizar_tema(c.tema) == normalizar_tema(tema)), None
        )
        if mismo_tema is not None or len(abiertas) < self._settings.limite_temas_gratis:
            return mismo_tema
        raise FuncionPremiumError(
            "Con el plan gratuito puedes tener un tema abierto a la vez. Cierra el actual o pásate a Premium.",
            detalles={"capacidad": Capacidad.TEMAS_SIMULTANEOS.value},
        )

    def _propia(self, id_usuario: uuid.UUID, id_conversacion: uuid.UUID) -> Conversacion:
        conversacion = self._conversaciones.obtener_por_id(id_conversacion)
        if conversacion is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(conversacion.id_usuario, id_usuario)
        return conversacion

    def _mensajes_publicos(self, mensajes: list[Mensaje]) -> list[MensajePublico]:
        ids = [m.id_mensaje for m in mensajes]
        trabajos = {t.id_mensaje: t for t in self._trabajos_repo.listar_por_mensajes(ids)}
        archivos = {a.id_mensaje: a for a in self._archivos.listar_por_mensajes(ids)}
        return [
            MensajePublico(
                id_mensaje=m.id_mensaje,
                rol=m.rol,
                contenido=m.contenido,
                bloques=self._videos.hidratar(m.bloques or [])
                if m.rol == RolMensaje.TUTOR
                else None,
                fuentes=[fuente_publica(f) for f in self._fuentes.listar_por_mensaje(m.id_mensaje)],
                visual=self._trabajos.vista_opcional(trabajos.get(m.id_mensaje)),
                archivo=archivo_publico(archivos[m.id_mensaje])
                if m.id_mensaje in archivos
                else None,
                util=m.util,
                fecha=m.fecha,
            )
            for m in mensajes
        ]
