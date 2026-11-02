import uuid
from decimal import ROUND_HALF_UP, Decimal

from app.core.config import Settings
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import (
    RecursoNoEncontradoError,
    RespuestasIncompletasError,
    SesionYaEvaluadaError,
)
from app.fuentes.bloqueo import sin_bloqueadas
from app.models.enums import NivelCognitivo, OpcionRespuesta
from app.models.sesion_diagnostico import SesionDiagnostico
from app.repositories.diagnostico import SesionDiagnosticoRepository
from app.repositories.fuente import FuenteRepository
from app.schemas.diagnostico import RespuestasEntrada, ResultadoDiagnostico, ResultadoPregunta
from app.services.presentacion import fuente_publica
from app.validators.propiedad import validar_recurso_propio

DECIMALES_PUNTAJE = Decimal("0.01")


class EvaluacionService:
    def __init__(
        self,
        sesiones: SesionDiagnosticoRepository,
        fuentes: FuenteRepository,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._sesiones = sesiones
        self._fuentes = fuentes
        self._settings = settings
        self._uow = uow

    def evaluar(
        self, id_usuario: uuid.UUID, id_sesion: uuid.UUID, entrada: RespuestasEntrada
    ) -> ResultadoDiagnostico:
        sesion = self._sesion_pendiente(id_usuario, id_sesion)
        respuestas = self._respuestas_completas(sesion, entrada)
        aciertos = self._calificar(sesion, respuestas)
        puntaje = Decimal(aciertos) / Decimal(sesion.total_preguntas)
        sesion.puntaje_diagnostico = puntaje.quantize(DECIMALES_PUNTAJE, rounding=ROUND_HALF_UP)
        sesion.nivel_estimado = self._nivel(float(puntaje))
        self._uow.commit()
        return self._resultado(sesion, aciertos)

    def _sesion_pendiente(self, id_usuario: uuid.UUID, id_sesion: uuid.UUID) -> SesionDiagnostico:
        sesion = self._sesiones.obtener_con_preguntas(id_sesion)
        if sesion is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(sesion.id_usuario, id_usuario)
        if sesion.nivel_estimado is not None:
            raise SesionYaEvaluadaError()
        return sesion

    @staticmethod
    def _respuestas_completas(
        sesion: SesionDiagnostico, entrada: RespuestasEntrada
    ) -> dict[uuid.UUID, OpcionRespuesta]:
        respuestas = {r.id_pregunta: r.respuesta for r in entrada.respuestas}
        if set(respuestas) != {p.id_pregunta for p in sesion.preguntas}:
            raise RespuestasIncompletasError()
        return respuestas

    @staticmethod
    def _calificar(sesion: SesionDiagnostico, respuestas: dict[uuid.UUID, OpcionRespuesta]) -> int:
        for pregunta in sesion.preguntas:
            pregunta.respuesta_usuario = respuestas[pregunta.id_pregunta]
            pregunta.es_correcta = pregunta.respuesta_usuario == pregunta.respuesta_correcta
        return sum(1 for p in sesion.preguntas if p.es_correcta)

    def _nivel(self, puntaje: float) -> NivelCognitivo:
        if puntaje < self._settings.umbral_basico:
            return NivelCognitivo.BASICO
        if puntaje < self._settings.umbral_intermedio:
            return NivelCognitivo.INTERMEDIO
        return NivelCognitivo.AVANZADO

    def _resultado(self, sesion: SesionDiagnostico, aciertos: int) -> ResultadoDiagnostico:
        ids = [p.id_fuente for p in sesion.preguntas if p.id_fuente]
        guardadas = self._fuentes.listar_por_ids(ids)
        fuentes = {
            f.id_fuente: f
            for f in sin_bloqueadas(guardadas, self._settings.fuentes_dominios_bloqueados)
        }
        assert sesion.nivel_estimado is not None and sesion.puntaje_diagnostico is not None
        return ResultadoDiagnostico(
            id_sesion=sesion.id_sesion,
            nivel_estimado=sesion.nivel_estimado,
            puntaje=sesion.puntaje_diagnostico,
            aciertos=aciertos,
            total_preguntas=sesion.total_preguntas,
            resultados=[
                ResultadoPregunta(
                    id_pregunta=p.id_pregunta,
                    respuesta_usuario=p.respuesta_usuario,
                    es_correcta=bool(p.es_correcta),
                    respuesta_correcta=p.respuesta_correcta,
                    fuente=fuente_publica(fuentes[p.id_fuente]) if p.id_fuente in fuentes else None,
                )
                for p in sesion.preguntas
                if p.respuesta_usuario is not None
            ],
        )
