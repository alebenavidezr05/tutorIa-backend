"""Verifica la conexión con la API de Claude: una petición mínima a cada modelo configurado.

Distingue llave inválida, modelo no disponible para la cuenta y falta de conexión. Nunca
imprime la llave. Uso: python -m app.scripts.probar_llm
"""

import sys

from app.core.config import get_settings
from app.llm.anthropic_client import AnthropicClient, ResultadoPrueba
from app.llm.base import BloqueSistema, LLMSolicitud, NivelModelo, TareaLLM
from app.scripts._comun import preparar_consola

MAX_TOKENS_PRUEBA = 1024


def _solicitud(nivel: NivelModelo) -> LLMSolicitud:
    return LLMSolicitud.simple(
        TareaLLM.CUESTIONARIO,
        (BloqueSistema("Responde solo con la palabra: ok"),),
        "Prueba de conexión.",
        nivel,
        MAX_TOKENS_PRUEBA,
    )


def _imprimir(resultado: ResultadoPrueba) -> None:
    if resultado.exito:
        print(
            f"[OK] modelo={resultado.modelo} latencia_ms={resultado.latencia_ms} "
            f"tokens_entrada={resultado.tokens_entrada} tokens_salida={resultado.tokens_salida}"
        )
    else:
        print(f"[FALLA] modelo={resultado.modelo}: {resultado.error}")


def main() -> int:
    preparar_consola()
    settings = get_settings()
    if settings.llm_provider != "anthropic":
        print(
            "LLM_PROVIDER no es 'anthropic': no hay nada que probar (se usa el cliente simulado)."
        )
        return 1
    cliente = AnthropicClient(settings)
    resultados = [cliente.probar_conexion(_solicitud(nivel)) for nivel in NivelModelo]
    cliente.cerrar()
    for resultado in resultados:
        _imprimir(resultado)
    return 0 if all(r.exito for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
