"""Patrones de inyección de prompt compartidos por la capa 1 del diagnóstico y del chat."""

from app.validators.texto import compilar

PATRONES_INYECCION = compilar(
    r"ignora\w* (todas )?(las |tus )?(instrucciones|reglas|indicaciones)",
    r"olvida\w* (todas )?(las |tus )?(instrucciones|reglas|indicaciones)",
    r"ignore (all |the |your )?(previous |prior )?instructions",
    r"(actua|comportate) como si no tuvieras (reglas|restricciones)",
    r"(system prompt|prompt del sistema|mensaje del sistema)",
    r"(modo|mode) (desarrollador|developer|dan|sin restricciones)",
    r"</?\s*(system|instrucciones|mensaje_estudiante|perfil_estudiante|resultado_herramienta)\s*>",
    r"jailbreak",
)
