import uuid

from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import RecursoNoEncontradoError, SesionYaEvaluadaError
from app.llm.base import LLMClient, LLMSolicitud, TareaLLM
from app.llm.parser import LLMResponseParser
from app.llm.prompts import PromptBuilder
from app.llm.selector_modelo import SelectorModelo
from app.models.enums import NivelCognitivo, OpcionRespuesta, OperacionIA
from app.models.fuente import Fuente
from app.models.pregunta_diagnostico import PreguntaDiagnostico
from app.models.sesion_diagnostico import SesionDiagnostico
from app.models.usuario import Usuario
from app.repositories.diagnostico import SesionDiagnosticoRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.bloques import PreguntaGenerada
from app.schemas.diagnostico import (
    CrearDiagnosticoEntrada,
    CuestionarioPublico,
    OpcionesPublicas,
    PreguntaPublica,
)
from app.services.consumo_service import ConsumoService
from app.services.estudiante import perfil_estudiante
from app.services.fuentes.fuentes_service import ContextoFuentes, FuentesService
from app.validators.cuestionario import CuestionarioValidator
from app.validators.propiedad import validar_recurso_propio
from app.validators.tema import validar_tema

MAX_MATERIA = 100
MATERIA_POR_DEFECTO = "General"
# Antes del diagnóstico no se conoce el nivel: se exige la autoridad mínima más baja.
NIVEL_PREVIO_AL_DIAGNOSTICO = NivelCognitivo.BASICO


class DiagnosticoService:
    def __init__(
        self,
        sesiones: SesionDiagnosticoRepository,
        usuarios: UsuarioRepository,
        fuentes: FuentesService,
        llm: LLMClient,
        prompts: PromptBuilder,
        parser: LLMResponseParser,
        validador: CuestionarioValidator,
        selector: SelectorModelo,
        consumo: ConsumoService,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._sesiones = sesiones
        self._usuarios = usuarios
        self._fuentes = fuentes
        self._llm = llm
        self._prompts = prompts
        self._parser = parser
        self._validador = validador
        self._selector = selector
        self._consumo = consumo
        self._settings = settings
        self._uow = uow

    def crear_sesion(
        self, id_usuario: uuid.UUID, entrada: CrearDiagnosticoEntrada
    ) -> CuestionarioPublico:
        tema = validar_tema(entrada.tema)
        usuario = self._usuario(id_usuario)
        fuentes = self._fuentes.recopilar_suficientes(
            tema, ContextoFuentes(NIVEL_PREVIO_AL_DIAGNOSTICO, usuario.tipo_nivel)
        )
        materia, preguntas = self._generar(usuario, tema, fuentes)
        self._fuentes.persistir_pendientes()
        sesion = self._guardar(id_usuario, tema, materia, preguntas)
        self._uow.commit()
        return self._publico(sesion)

    def obtener_cuestionario(
        self, id_usuario: uuid.UUID, id_sesion: uuid.UUID
    ) -> CuestionarioPublico:
        sesion = self._sesiones.obtener_con_preguntas(id_sesion)
        if sesion is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(sesion.id_usuario, id_usuario)
        if sesion.nivel_estimado is not None:
            raise SesionYaEvaluadaError()
        return self._publico(sesion)

    def _usuario(self, id_usuario: uuid.UUID) -> Usuario:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        return usuario

    def _generar(
        self, usuario: Usuario, tema: str, fuentes: list[Fuente]
    ) -> tuple[str, list[PreguntaGenerada]]:
        estudiante = perfil_estudiante(usuario, self._settings)
        texto = self._prompts.cuestionario(
            tema,
            estudiante.nivel_educativo,
            estudiante.tipo_nivel,
            estudiante.grupo_edad,
            self._fuentes.a_contexto(fuentes),
            self._settings.diagnostico_preguntas,
        )
        solicitud = LLMSolicitud.simple(
            TareaLLM.CUESTIONARIO,
            self._prompts.system(),
            texto,
            self._selector.para_tarea(TareaLLM.CUESTIONARIO),
            self._settings.llm_max_tokens_cuestionario,
        )
        respuesta = self._llm.completar(solicitud)
        self._consumo.registrar_llm(usuario.id_usuario, OperacionIA.CUESTIONARIO, respuesta)
        cuestionario = self._parser.parse_cuestionario(respuesta.texto())
        preguntas = self._validador.validar(cuestionario, {f.id_fuente for f in fuentes})
        return (cuestionario.materia or MATERIA_POR_DEFECTO)[:MAX_MATERIA], preguntas

    def _guardar(
        self, id_usuario: uuid.UUID, tema: str, materia: str, preguntas: list[PreguntaGenerada]
    ) -> SesionDiagnostico:
        sesion = SesionDiagnostico(
            id_usuario=id_usuario,
            tema=tema,
            materia=materia,
            total_preguntas=len(preguntas),
            fecha_creacion=ahora_utc(),
            preguntas=[
                PreguntaDiagnostico(
                    enunciado=p.enunciado,
                    opcion_a=p.opciones.a,
                    opcion_b=p.opciones.b,
                    opcion_c=p.opciones.c,
                    opcion_d=p.opciones.d,
                    respuesta_correcta=OpcionRespuesta(p.respuesta_correcta.upper()),
                    id_fuente=p.id_fuente,
                    orden=orden,
                )
                for orden, p in enumerate(preguntas, start=1)
            ],
        )
        return self._sesiones.agregar(sesion)

    @staticmethod
    def _publico(sesion: SesionDiagnostico) -> CuestionarioPublico:
        return CuestionarioPublico(
            id_sesion=sesion.id_sesion,
            tema=sesion.tema,
            materia=sesion.materia,
            preguntas=[
                PreguntaPublica(
                    id_pregunta=p.id_pregunta,
                    orden=p.orden,
                    enunciado=p.enunciado,
                    opciones=OpcionesPublicas(
                        a=p.opcion_a, b=p.opcion_b, c=p.opcion_c, d=p.opcion_d
                    ),
                )
                for p in sesion.preguntas
            ],
        )
