"""Textos fijos que pone el sistema, nunca el modelo. Revisión humana obligatoria antes de producción."""

from app.core.config import LineaAyuda

MENSAJE_NO_ACADEMICO = (
    "Esa consulta no es sobre estudio, así que no puedo ayudarte con ella. Cuéntame qué tema "
    "quieres aprender o repasar y lo trabajamos juntos."
)
MENSAJE_RECHAZO = (
    "No puedo ayudarte con ese contenido. Si tienes una duda de estudio, escríbela y la resolvemos."
)
PLANTILLA_APOYO = (
    "Lamento que estés pasando por algo difícil. No estás solo o sola: habla ahora con una "
    "persona de confianza, como alguien de tu familia, un profesor o un orientador. Si necesitas "
    "ayuda inmediata, puedes comunicarte con: {lineas}."
)
AVISO_IA = "{tutor} es una inteligencia artificial, no una persona."
AVISO_PRECISION = "Las respuestas de una IA pueden tener errores. Contrástalas con las fuentes citadas y con tu profesor."
AVISO_ILUSTRACION_IA = (
    "Ilustración generada por IA. Puede contener imprecisiones; verifica los conceptos importantes."
)
AVISO_RESUMEN_SESION = "Las respuestas las genera una IA; contrástalas con estas fuentes."
RESPALDO_TEXTO = (
    "Vamos paso a paso. Cuéntame qué parte del tema ya entiendes y en cuál te quedas atascado; "
    "con eso te propongo una pista para avanzar."
)
RESPALDO_PREGUNTA = "¿Qué parte del tema quieres que repasemos primero?"


def mensaje_apoyo(lineas: list[LineaAyuda]) -> str:
    return PLANTILLA_APOYO.format(
        lineas="; ".join(f"{linea.nombre} ({linea.numero})" for linea in lineas)
    )
