from typing import Final, Literal

# Regla no negociable (§2.20): la calidad de las ilustraciones IA es SIEMPRE baja. No es
# configurable ni la puede cambiar la API, el modelo de lenguaje o el texto del estudiante.
CALIDAD_IMAGEN_IA: Final[Literal["low"]] = "low"

PLANTILLA_PROMPT_IMAGEN = (
    "Ilustración educativa, estilo plano y claro, apropiada para estudiantes de {grupo_edad}. "
    "Sin texto, letras, números ni etiquetas dentro de la imagen. Sin personas reales "
    "identificables. Concepto: {descripcion}"
)
DESCRIPCION_EDAD_IMAGEN = {
    "ADOLESCENTE_TEMPRANO": "13 a 14 años",
    "ADOLESCENTE": "15 a 17 años",
    "ADULTO": "educación superior",
}


def construir_prompt_imagen(descripcion_visual: str, grupo_edad: str) -> str:
    """Función pura: solo recibe la descripción validada, nunca el mensaje ni datos del estudiante."""
    return PLANTILLA_PROMPT_IMAGEN.format(
        grupo_edad=DESCRIPCION_EDAD_IMAGEN.get(grupo_edad, DESCRIPCION_EDAD_IMAGEN["ADOLESCENTE"]),
        descripcion=descripcion_visual,
    )
