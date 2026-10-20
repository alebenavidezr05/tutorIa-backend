from dataclasses import dataclass

from app.models.enums import FormatoExplicacion, NivelCognitivo


@dataclass(frozen=True)
class PoliticaNivel:
    """Fuente única de lo que cambia según el nivel cognitivo (Bloom revisada)."""

    nivel: NivelCognitivo
    procesos_bloom: str
    instrucciones: str
    formatos_sugeridos: tuple[FormatoExplicacion, ...]
    tipos_pregunta: tuple[str, ...]
    permite_archivos: bool


POLITICAS = {
    NivelCognitivo.BASICO: PoliticaNivel(
        nivel=NivelCognitivo.BASICO,
        procesos_bloom="recordar y comprender",
        instrucciones=(
            "Trabaja definiciones clave, ejemplos concretos y analogías simples. Cierra con "
            "preguntas de comprensión literal."
        ),
        formatos_sugeridos=(
            FormatoExplicacion.EJEMPLO,
            FormatoExplicacion.ANALOGIA,
            FormatoExplicacion.VISUAL,
        ),
        tipos_pregunta=("comprensión literal", "identificación de conceptos"),
        permite_archivos=False,
    ),
    NivelCognitivo.INTERMEDIO: PoliticaNivel(
        nivel=NivelCognitivo.INTERMEDIO,
        procesos_bloom="aplicar y analizar",
        instrucciones=(
            "Propón problemas de aplicación, comparaciones y análisis de casos, con preguntas "
            "orientadoras que guían sin revelar la solución."
        ),
        formatos_sugeridos=(FormatoExplicacion.PASO_A_PASO, FormatoExplicacion.EJEMPLO),
        tipos_pregunta=("aplicación", "comparación", "análisis de casos"),
        permite_archivos=False,
    ),
    NivelCognitivo.AVANZADO: PoliticaNivel(
        nivel=NivelCognitivo.AVANZADO,
        procesos_bloom="evaluar y crear",
        instrucciones=(
            "Plantea retos de diseño o argumentación, propuestas originales y criterios de "
            "autoevaluación. Pide al estudiante que produzca sus propias explicaciones o "
            "resúmenes; puede entregarlos como texto, PDF o imagen."
        ),
        formatos_sugeridos=(FormatoExplicacion.FORMAL, FormatoExplicacion.TEORIA),
        tipos_pregunta=("evaluación", "argumentación", "diseño"),
        permite_archivos=True,
    ),
}


def politica_de(nivel: NivelCognitivo) -> PoliticaNivel:
    return POLITICAS[nivel]
