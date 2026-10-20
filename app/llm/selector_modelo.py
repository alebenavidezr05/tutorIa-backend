from dataclasses import dataclass

from app.llm.base import NivelModelo, TareaLLM
from app.models.enums import NivelCognitivo
from app.validators.texto import compilar, contiene_alguno, normalizar_para_comparar

PESO_NIVEL = {NivelCognitivo.BASICO: 0, NivelCognitivo.INTERMEDIO: 1, NivelCognitivo.AVANZADO: 2}
PESO_INTENCION_ANALITICA = 2
PESO_PASO_A_PASO = 1
PESO_POR_NO_ENTENDI = 1
MAX_PESO_NO_ENTENDI = 2
PESO_ARCHIVO = 2
PESO_MENSAJE_LARGO = 1
PATRONES_ANALITICOS = compilar(
    r"\bcompar\w*",
    r"\banaliz\w*",
    r"\bdemuestr\w*",
    r"\bdemostr\w*",
    r"\bjustific\w*",
    r"\bevalu\w*",
    r"\bdisen\w*",
)
PATRONES_PASO_A_PASO = compilar(r"\bpaso a paso\b", r"\bpaso por paso\b")
NIVEL_POR_TAREA = {
    TareaLLM.CUESTIONARIO: NivelModelo.SENCILLO,
    TareaLLM.CONSOLIDACION: NivelModelo.SENCILLO,
    TareaLLM.PLAN: NivelModelo.COMPLEJO,
}


@dataclass(frozen=True)
class SenalesComplejidad:
    mensaje: str
    nivel_cognitivo: NivelCognitivo
    no_entendi_recientes: int
    tiene_archivo: bool


class SelectorModelo:
    """Haiku por defecto; Sonnet solo cuando las señales lo justifican. Sin llamadas a modelos."""

    def __init__(self, umbral: int, palabras_largo: int) -> None:
        self._umbral = umbral
        self._palabras_largo = palabras_largo

    def para_tarea(self, tarea: TareaLLM) -> NivelModelo:
        return NIVEL_POR_TAREA[tarea]

    def elegir(self, senales: SenalesComplejidad) -> NivelModelo:
        if self.puntuar(senales) >= self._umbral:
            return NivelModelo.COMPLEJO
        return NivelModelo.SENCILLO

    def puntuar(self, senales: SenalesComplejidad) -> int:
        texto = normalizar_para_comparar(senales.mensaje)
        return (
            PESO_NIVEL[senales.nivel_cognitivo]
            + (PESO_INTENCION_ANALITICA if contiene_alguno(texto, PATRONES_ANALITICOS) else 0)
            + (PESO_PASO_A_PASO if contiene_alguno(texto, PATRONES_PASO_A_PASO) else 0)
            + min(senales.no_entendi_recientes * PESO_POR_NO_ENTENDI, MAX_PESO_NO_ENTENDI)
            + (PESO_ARCHIVO if senales.tiene_archivo else 0)
            + (PESO_MENSAJE_LARGO if len(texto.split()) > self._palabras_largo else 0)
        )
