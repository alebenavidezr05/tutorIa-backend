"""Derivaciones puras de los bloques del tutor: formatos usados, texto plano y citas."""

import uuid
from collections.abc import Sequence

from app.models.enums import FormatoExplicacion
from app.schemas.bloques import (
    BLOQUES_CON_HECHOS,
    BloqueAnalogia,
    BloqueEjemplo,
    BloqueFormula,
    BloquePasos,
    BloquePreguntaComprension,
    BloquePreguntaResumen,
    BloqueTexto,
    BloqueTutor,
    BloqueVideo,
)

FORMATO_POR_BLOQUE: dict[type, FormatoExplicacion] = {
    BloqueEjemplo: FormatoExplicacion.EJEMPLO,
    BloquePasos: FormatoExplicacion.PASO_A_PASO,
    BloqueVideo: FormatoExplicacion.VISUAL,
    BloqueAnalogia: FormatoExplicacion.ANALOGIA,
    BloqueFormula: FormatoExplicacion.FORMAL,
}


def formatos_usados(bloques: Sequence[BloqueTutor], tiene_visual: bool) -> list[FormatoExplicacion]:
    formatos = {FORMATO_POR_BLOQUE[type(b)] for b in bloques if type(b) in FORMATO_POR_BLOQUE}
    if tiene_visual:
        formatos.add(FormatoExplicacion.VISUAL)
    if not formatos and any(isinstance(b, BloqueTexto) for b in bloques):
        formatos.add(FormatoExplicacion.TEORIA)
    return sorted(formatos)


def texto_plano(bloque: BloqueTutor) -> str:
    match bloque:
        case BloqueTexto(contenido=c) | BloqueAnalogia(contenido=c):
            return c
        case BloquePasos(titulo=t, pasos=p):
            return f"{t}: " + " ".join(f"{i}. {paso}" for i, paso in enumerate(p, start=1))
        case BloqueEjemplo(titulo=t, contenido=c):
            return f"{t}: {c}"
        case BloqueFormula(latex=latex, descripcion=d):
            return f"{d} ({latex})"
        case BloquePreguntaComprension(enunciado=e) | BloquePreguntaResumen(enunciado=e):
            return e
        case BloqueVideo():
            return "[Video recomendado]"
    return ""


def contenido_plano(bloques: Sequence[BloqueTutor]) -> str:
    return "\n".join(t for t in (texto_plano(b) for b in bloques) if t)


def fuentes_citadas(bloques: Sequence[BloqueTutor]) -> set[uuid.UUID]:
    return {f for b in bloques if isinstance(b, BLOQUES_CON_HECHOS) for f in b.fuentes}
