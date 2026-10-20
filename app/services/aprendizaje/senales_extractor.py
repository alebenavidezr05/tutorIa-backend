"""Señales pedagógicas del mensaje del estudiante: funciones puras, sin LLM, con y sin tildes."""

import re
from dataclasses import dataclass

from app.models.enums import FormatoExplicacion, IntencionMensaje, TipoEvento
from app.validators.mensaje import clasificar_intencion
from app.validators.texto import compilar, contiene_alguno, normalizar_para_comparar

PATRONES_POR_EVENTO: dict[TipoEvento, tuple[re.Pattern[str], ...]] = {
    TipoEvento.PIDE_EJEMPLO: compilar(r"\bejemplos?\b", r"\bun caso\b", r"\bpor ejemplo\b"),
    TipoEvento.PIDE_VISUAL: compilar(
        r"\bimagen(es)?\b",
        r"\bdibuj\w*",
        r"\bdiagrama\w*",
        r"\bgrafic\w*",
        r"\besquema\w*",
        r"\bmapa conceptual\b",
        r"\bmuestram\w*",
        r"\bvisual\w*",
        r"\bvideo\w*",
    ),
    TipoEvento.PIDE_PASO_A_PASO: compilar(
        r"\bpaso a paso\b", r"\bpaso por paso\b", r"\bpor pasos\b"
    ),
    TipoEvento.PIDE_SIMPLIFICAR: compilar(
        r"\bmas (facil|simple|sencill)\w*",
        r"\bsimplific\w*",
        r"\bpalabras (simples|sencillas)\b",
        r"\bcomo si (tuviera|fuera)\b",
    ),
    TipoEvento.PIDE_MAS_DETALLE: compilar(
        r"\bmas detall\w*",
        r"\bprofundiz\w*",
        r"\bexplic\w* mas\b",
        r"\ben detalle\b",
        r"\bmas a fondo\b",
    ),
    TipoEvento.PIDE_RESUMEN: compilar(r"\bresum\w*", r"\ben pocas palabras\b", r"\bbreve\w*"),
    TipoEvento.NO_ENTENDIO: compilar(
        r"\bno (le |lo |la )?entend\w*",
        r"\bno entiendo\b",
        r"\bno me queda claro\b",
        r"\bsigo sin entender\b",
        r"\bconfundid\w*",
        r"\bno capto\b",
    ),
}
FORMATO_POR_EVENTO = {
    TipoEvento.PIDE_EJEMPLO: FormatoExplicacion.EJEMPLO,
    TipoEvento.PIDE_VISUAL: FormatoExplicacion.VISUAL,
    TipoEvento.PIDE_PASO_A_PASO: FormatoExplicacion.PASO_A_PASO,
}
# Lista corta y ampliable de términos técnicos frecuentes en colegio y universidad.
VOCABULARIO_TECNICO = frozenset(
    {
        "funcion",
        "derivada",
        "integral",
        "ecuacion",
        "teorema",
        "hipotesis",
        "variable",
        "molecula",
        "celula",
        "algoritmo",
        "vector",
        "matriz",
        "fotosintesis",
        "mitosis",
        "polinomio",
        "logaritmo",
        "energia",
        "velocidad",
        "aceleracion",
        "estequiometria",
        "termodinamica",
        "probabilidad",
        "estadistica",
        "sintaxis",
        "metafora",
    }
)
UMBRAL_REPREGUNTA = 0.8
_PATRON_PALABRA = re.compile(r"\w+")


@dataclass(frozen=True)
class SenalesMensaje:
    eventos: tuple[TipoEvento, ...]
    intencion: IntencionMensaje
    longitud_palabras: int
    usa_vocabulario_tecnico: bool
    repite_pregunta: bool

    @property
    def formatos_pedidos(self) -> tuple[FormatoExplicacion, ...]:
        return tuple(FORMATO_POR_EVENTO[e] for e in self.eventos if e in FORMATO_POR_EVENTO)


def _palabras(texto: str) -> set[str]:
    return set(_PATRON_PALABRA.findall(normalizar_para_comparar(texto)))


def _similitud(a: str, b: str) -> float:
    pa, pb = _palabras(a), _palabras(b)
    return len(pa & pb) / len(pa | pb) if pa | pb else 0.0


class SenalesExtractor:
    def extraer(self, texto: str, mensaje_anterior: str | None) -> SenalesMensaje:
        normalizado = normalizar_para_comparar(texto)
        intencion = clasificar_intencion(texto)
        repite = (
            mensaje_anterior is not None
            and _similitud(texto, mensaje_anterior) >= UMBRAL_REPREGUNTA
        )
        eventos = [
            e
            for e, patrones in PATRONES_POR_EVENTO.items()
            if contiene_alguno(normalizado, patrones)
        ]
        if intencion == IntencionMensaje.RESOLVER_TAREA:
            eventos.append(TipoEvento.PIDE_RESPUESTA_DIRECTA)
        if repite:
            eventos.append(TipoEvento.REPREGUNTA)
        return SenalesMensaje(
            eventos=tuple(eventos),
            intencion=intencion,
            longitud_palabras=len(normalizado.split()),
            usa_vocabulario_tecnico=bool(_palabras(texto) & VOCABULARIO_TECNICO),
            repite_pregunta=repite,
        )
