"""Única fuente de los patrones de entrega directa de respuestas (los usan plan y tutor)."""

from app.validators.texto import compilar, contiene_alguno, normalizar_para_comparar

PATRON_LA_RESPUESTA_ES = r"\bla respuesta (correcta )?es\b"
PATRON_SOLUCION = r"\bsolucion\s*:"
PATRON_RESULTADO_FINAL = r"\bresultado final\b"
PATRON_RESPUESTA_CORRECTA = r"\brespuesta correcta\b"
PATRON_RESPUESTA_FINAL = r"\brespuesta final\b"

PATRONES_ENTREGA_DIRECTA = compilar(
    PATRON_LA_RESPUESTA_ES,
    PATRON_SOLUCION,
    PATRON_RESULTADO_FINAL,
    PATRON_RESPUESTA_CORRECTA,
    PATRON_RESPUESTA_FINAL,
)


def contiene_entrega_directa(texto: str) -> bool:
    return contiene_alguno(normalizar_para_comparar(texto), PATRONES_ENTREGA_DIRECTA)
