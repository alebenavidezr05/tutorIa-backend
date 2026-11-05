import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DIRECTORIO_LEGAL = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TextosLegales:
    politica: str
    vigente_desde: str
    finalidades: dict[str, dict[str, Any]]
    # Frase única que lee y confirma el acudiente (pendiente de revisión del abogado).
    autorizacion_acudiente: str


def cargar_textos_legales(version: str) -> TextosLegales:
    politica = (DIRECTORIO_LEGAL / f"politica_tratamiento_v{version}.md").read_text(
        encoding="utf-8"
    )
    datos = json.loads(
        (DIRECTORIO_LEGAL / f"consentimientos_v{version}.json").read_text(encoding="utf-8")
    )
    return TextosLegales(
        politica,
        datos["vigente_desde"],
        datos["finalidades"],
        datos["autorizacion_acudiente"]["texto"],
    )
