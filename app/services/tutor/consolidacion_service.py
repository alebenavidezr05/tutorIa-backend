import json
import logging
import uuid

from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import LLMError, LLMRespuestaInvalidaError, RecursoNoEncontradoError
from app.llm.base import LLMClient, LLMSolicitud, MensajeLLM, TareaLLM
from app.llm.herramientas import ACTUALIZAR_PERFIL, herramienta_actualizar_perfil
from app.llm.parser import LLMResponseParser
from app.llm.prompts_tutor import ConsolidacionPromptBuilder
from app.llm.selector_modelo import SelectorModelo
from app.models.conversacion import Conversacion
from app.models.enums import EstadoConversacion, OperacionIA, RolMensaje
from app.models.perfil_aprendizaje import PerfilAprendizaje
from app.repositories.conversacion import (
    ConversacionRepository,
    EventoAprendizajeRepository,
    MensajeRepository,
    PerfilAprendizajeRepository,
)
from app.schemas.bloques import ActualizacionPerfil
from app.schemas.conversacion import ResumenSesion
from app.services.aprendizaje.perfil_aprendizaje_service import PerfilAprendizajeService
from app.services.consumo_service import ConsumoService
from app.services.fuentes.referencias_service import ReferenciasService
from app.services.seguridad.textos import AVISO_RESUMEN_SESION
from app.validators.perfil import fusionar_tema
from app.validators.propiedad import validar_recurso_propio

logger = logging.getLogger(__name__)

ETIQUETA_ROL = {RolMensaje.USUARIO: "Estudiante", RolMensaje.TUTOR: "Tutor"}
RESUMEN_SIN_CONSOLIDAR = "La sesión se cerró. El resumen se completará más adelante."


class ConsolidacionService:
    """Cierra la conversación y consolida el perfil con el modelo sencillo. Si el LLM falla, la
    conversación igual queda cerrada con `consolidada=False` y se reintenta en el próximo cierre."""

    def __init__(
        self,
        conversaciones: ConversacionRepository,
        mensajes: MensajeRepository,
        eventos: EventoAprendizajeRepository,
        perfiles_repo: PerfilAprendizajeRepository,
        perfiles: PerfilAprendizajeService,
        llm: LLMClient,
        prompts: ConsolidacionPromptBuilder,
        parser: LLMResponseParser,
        selector: SelectorModelo,
        consumo: ConsumoService,
        referencias: ReferenciasService,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._conversaciones = conversaciones
        self._mensajes = mensajes
        self._eventos = eventos
        self._perfiles_repo = perfiles_repo
        self._perfiles = perfiles
        self._llm = llm
        self._prompts = prompts
        self._parser = parser
        self._selector = selector
        self._consumo = consumo
        self._referencias = referencias
        self._settings = settings
        self._uow = uow

    def cerrar(self, id_usuario: uuid.UUID, id_conversacion: uuid.UUID) -> ResumenSesion:
        conversacion = self._conversaciones.obtener_por_id(id_conversacion)
        if conversacion is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(conversacion.id_usuario, id_usuario)
        self.consolidar(conversacion)
        self._uow.commit()
        return ResumenSesion(
            resumen=conversacion.resumen or RESUMEN_SIN_CONSOLIDAR,
            referencias=self._referencias.de_conversacion(id_usuario, id_conversacion),
            aviso=AVISO_RESUMEN_SESION,
        )

    def consolidar(self, conversacion: Conversacion) -> None:
        """No confirma. Idempotente: una conversación ya consolidada no vuelve a llamar al LLM.
        Los cambios se aplican después de la llamada: no queda escritura abierta durante ella."""
        if conversacion.consolidada:
            conversacion.estado = EstadoConversacion.CERRADA
            return
        try:
            actualizacion = self._solicitar_actualizacion(conversacion)
        except LLMError as exc:
            logger.warning("consolidacion_pendiente tipo=%s", type(exc).__name__)
            conversacion.estado = EstadoConversacion.CERRADA
            conversacion.consolidada = False
            return
        conversacion.estado = EstadoConversacion.CERRADA
        self._aplicar(conversacion, actualizacion)

    def _solicitar_actualizacion(self, conversacion: Conversacion) -> ActualizacionPerfil:
        solicitud = LLMSolicitud(
            tarea=TareaLLM.CONSOLIDACION,
            system=self._prompts.system(),
            mensajes=(MensajeLLM.usuario(self._entrada(conversacion)),),
            nivel_modelo=self._selector.para_tarea(TareaLLM.CONSOLIDACION),
            max_tokens=self._settings.llm_max_tokens_consolidacion,
            herramientas=(herramienta_actualizar_perfil(),),
            herramienta_forzada=ACTUALIZAR_PERFIL,
        )
        respuesta = self._llm.completar(solicitud)
        self._consumo.registrar_llm(conversacion.id_usuario, OperacionIA.CONSOLIDACION, respuesta)
        uso = next((u for u in respuesta.usos_herramienta() if u.nombre == ACTUALIZAR_PERFIL), None)
        if uso is None:
            raise LLMRespuestaInvalidaError()
        return self._parser.parse_actualizacion_perfil(uso.entrada)

    def _entrada(self, conversacion: Conversacion) -> str:
        perfil = self._perfil_activo(conversacion.id_usuario)
        preferencias = self._perfiles.preferencias(perfil).model_dump(mode="json") if perfil else {}
        conteo = self._eventos.contar_por_tipo_en_conversacion(conversacion.id_conversacion)
        return self._prompts.entrada(
            self._transcripcion(conversacion),
            json.dumps(preferencias, ensure_ascii=False),
            json.dumps({t.value: n for t, n in conteo.items()}, ensure_ascii=False),
        )

    def _transcripcion(self, conversacion: Conversacion) -> str:
        lineas = [
            f"{ETIQUETA_ROL[m.rol]}: {m.contenido}"
            for m in self._mensajes.listar_por_conversacion(conversacion.id_conversacion)
        ]
        texto = "\n".join(lineas)
        # Se conserva el final: es lo más reciente y lo más útil para el perfil.
        return texto[-self._settings.consolidacion_max_caracteres :]

    def _perfil_activo(self, id_usuario: uuid.UUID) -> PerfilAprendizaje | None:
        perfil = self._perfiles_repo.obtener_por_usuario(id_usuario)
        return perfil if perfil is not None and perfil.personalizacion_activa else None

    def _aplicar(self, conversacion: Conversacion, actualizacion: ActualizacionPerfil) -> None:
        conversacion.resumen = actualizacion.resumen_conversacion
        conversacion.consolidada = True
        perfil = self._perfil_activo(conversacion.id_usuario)
        if perfil is None:
            return
        preferencias = fusionar_tema(
            self._perfiles.preferencias(perfil),
            conversacion.tema,
            actualizacion.dificultades,
            actualizacion.fortalezas,
            ahora_utc(),
        )
        preferencias = preferencias.model_copy(
            update={
                "detalle": actualizacion.detalle,
                "ritmo": actualizacion.ritmo,
                "resumen": actualizacion.resumen_perfil,
            }
        )
        self._perfiles.guardar(perfil, preferencias)
        perfil.version += 1
