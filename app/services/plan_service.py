import uuid
from dataclasses import dataclass

from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import (
    LLMRespuestaInvalidaError,
    RecursoNoEncontradoError,
    SesionSinEvaluarError,
)
from app.llm.base import LLMClient, LLMSolicitud, TareaLLM
from app.llm.parser import LLMResponseParser
from app.llm.politica_nivel import politica_de
from app.llm.prompts import PromptBuilder
from app.llm.selector_modelo import SelectorModelo
from app.models.actividad import Actividad
from app.models.enums import CampoUso, EstadoPlan, NivelCognitivo, OperacionIA
from app.models.fuente import Fuente
from app.models.plan_estudio import PlanEstudio
from app.models.sesion_diagnostico import SesionDiagnostico
from app.models.usuario import Usuario
from app.repositories.archivo import ArchivoRepository
from app.repositories.diagnostico import SesionDiagnosticoRepository
from app.repositories.fuente import FuenteRepository
from app.repositories.plan import PlanEstudioRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.bloques import PlanGenerado
from app.schemas.plan import GenerarPlanEntrada, PlanDetalle
from app.services.consumo_service import ConsumoService
from app.services.estudiante import perfil_estudiante
from app.services.fuentes.fuentes_service import ContextoFuentes, FuentesService
from app.services.presentacion import actividad_publica, fuente_publica
from app.services.uso_service import UsoService
from app.validators.plan import PlanValidator
from app.validators.propiedad import validar_recurso_propio

MAX_TITULO = 200


@dataclass(frozen=True)
class PlanObtenido:
    plan: PlanGenerado
    valido: bool
    tokens_entrada: int
    tokens_salida: int


class PlanService:
    """Genera el plan con un bucle de regeneración: siempre responde, aunque sea sin validar."""

    def __init__(
        self,
        sesiones: SesionDiagnosticoRepository,
        planes: PlanEstudioRepository,
        usuarios: UsuarioRepository,
        fuentes_repo: FuenteRepository,
        archivos: ArchivoRepository,
        fuentes: FuentesService,
        llm: LLMClient,
        prompts: PromptBuilder,
        parser: LLMResponseParser,
        validador: PlanValidator,
        selector: SelectorModelo,
        uso: UsoService,
        consumo: ConsumoService,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._sesiones = sesiones
        self._planes = planes
        self._usuarios = usuarios
        self._fuentes_repo = fuentes_repo
        self._archivos = archivos
        self._fuentes = fuentes
        self._llm = llm
        self._prompts = prompts
        self._parser = parser
        self._validador = validador
        self._selector = selector
        self._uso = uso
        self._consumo = consumo
        self._settings = settings
        self._uow = uow

    def generar(self, id_usuario: uuid.UUID, entrada: GenerarPlanEntrada) -> PlanDetalle:
        sesion = self._sesion_evaluada(id_usuario, entrada.id_sesion)
        assert sesion.nivel_estimado is not None
        self._uso.asegurar_disponible(id_usuario, CampoUso.PLANES)
        usuario = self._usuario(id_usuario)
        fuentes = self._fuentes.recopilar_suficientes(
            sesion.tema, ContextoFuentes(sesion.nivel_estimado, usuario.tipo_nivel)
        )
        obtenido = self._generar_con_reintentos(
            usuario, sesion.tema, sesion.nivel_estimado, fuentes
        )
        self._uso.consumir(id_usuario, CampoUso.PLANES)
        plan = self._guardar(sesion, obtenido)
        self._fuentes.vincular_a_plan(plan.id_plan, self._fuentes_citadas(obtenido.plan, fuentes))
        self._uow.commit()
        return self._detalle(plan)

    def obtener(self, id_usuario: uuid.UUID, id_plan: uuid.UUID) -> PlanDetalle:
        plan = self._planes.obtener_con_actividades(id_plan)
        if plan is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(plan.id_usuario, id_usuario)
        return self._detalle(plan)

    def _sesion_evaluada(self, id_usuario: uuid.UUID, id_sesion: uuid.UUID) -> SesionDiagnostico:
        sesion = self._sesiones.obtener_por_id(id_sesion)
        if sesion is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(sesion.id_usuario, id_usuario)
        if sesion.nivel_estimado is None:
            raise SesionSinEvaluarError()
        return sesion

    def _usuario(self, id_usuario: uuid.UUID) -> Usuario:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        return usuario

    def _generar_con_reintentos(
        self, usuario: Usuario, tema: str, nivel: NivelCognitivo, fuentes: list[Fuente]
    ) -> PlanObtenido:
        ids_fuentes = {f.id_fuente for f in fuentes}
        tokens_entrada = tokens_salida = 0
        ultimo: PlanGenerado | None = None
        for intento in range(1 + self._settings.plan_max_reintentos):
            respuesta = self._llm.completar(self._solicitud(usuario, tema, nivel, fuentes, intento))
            self._consumo.registrar_llm(usuario.id_usuario, OperacionIA.PLAN, respuesta)
            tokens_entrada += respuesta.tokens_entrada
            tokens_salida += respuesta.tokens_salida
            plan = self._parser.intentar_parse_plan(respuesta.texto())
            ultimo = plan or ultimo
            if plan is not None and self._validador.validar(plan, ids_fuentes).valido:
                return PlanObtenido(plan, True, tokens_entrada, tokens_salida)
        if ultimo is None:
            raise LLMRespuestaInvalidaError()
        return PlanObtenido(ultimo, False, tokens_entrada, tokens_salida)

    def _solicitud(
        self,
        usuario: Usuario,
        tema: str,
        nivel: NivelCognitivo,
        fuentes: list[Fuente],
        intento: int,
    ) -> LLMSolicitud:
        estudiante = perfil_estudiante(usuario, self._settings)
        texto = self._prompts.plan(
            tema,
            politica_de(nivel),
            estudiante.nivel_educativo,
            estudiante.tipo_nivel,
            estudiante.grupo_edad,
            self._fuentes.a_contexto(fuentes),
            intento,
        )
        return LLMSolicitud.simple(
            TareaLLM.PLAN,
            self._prompts.system(),
            texto,
            self._selector.para_tarea(TareaLLM.PLAN),
            self._settings.llm_max_tokens_plan,
        )

    def _guardar(self, sesion: SesionDiagnostico, obtenido: PlanObtenido) -> PlanEstudio:
        assert sesion.nivel_estimado is not None
        generado = obtenido.plan
        actividades = [a.strip() for a in generado.actividades if a.strip()]
        plan = PlanEstudio(
            id_sesion=sesion.id_sesion,
            id_usuario=sesion.id_usuario,
            titulo=(generado.titulo.strip() or sesion.tema)[:MAX_TITULO],
            explicacion=generado.explicacion,
            tecnicas_estudio=[t.strip() for t in generado.tecnicas_estudio if t.strip()],
            nivel_bloom=sesion.nivel_estimado,
            tokens_entrada=obtenido.tokens_entrada,
            tokens_salida=obtenido.tokens_salida,
            validado=obtenido.valido,
            estado=EstadoPlan.GENERADO,
            fecha_generacion=ahora_utc(),
            actividades=[
                Actividad(numero_orden=i, enunciado=a) for i, a in enumerate(actividades, start=1)
            ],
        )
        return self._planes.agregar(plan)

    @staticmethod
    def _fuentes_citadas(plan: PlanGenerado, fuentes: list[Fuente]) -> list[uuid.UUID]:
        entregadas = {f.id_fuente for f in fuentes}
        citadas = [i for i in plan.fuentes_usadas if i in entregadas]
        # Si el modelo no citó, las fuentes entregadas como contexto igual se referencian.
        return citadas or list(entregadas)

    def _detalle(self, plan: PlanEstudio) -> PlanDetalle:
        archivos = {
            a.id_actividad: a
            for a in self._archivos.listar_por_actividades(
                [x.id_actividad for x in plan.actividades]
            )
        }
        return PlanDetalle(
            id_plan=plan.id_plan,
            id_sesion=plan.id_sesion,
            titulo=plan.titulo,
            explicacion=plan.explicacion,
            tecnicas_estudio=plan.tecnicas_estudio,
            nivel_bloom=plan.nivel_bloom,
            validado=plan.validado,
            estado=plan.estado,
            fecha_generacion=plan.fecha_generacion,
            actividades=[
                actividad_publica(a, archivos.get(a.id_actividad)) for a in plan.actividades
            ],
            fuentes=[fuente_publica(f) for f in self._fuentes_repo.listar_por_plan(plan.id_plan)],
            acepta_archivos=politica_de(plan.nivel_bloom).permite_archivos,
        )
