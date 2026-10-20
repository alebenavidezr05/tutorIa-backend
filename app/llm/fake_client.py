import json
import re
import uuid
from collections import deque
from typing import Any

from app.llm.base import (
    BloqueResultadoHerramienta,
    BloqueTextoLLM,
    BloqueUsoHerramienta,
    LLMClient,
    LLMRespuesta,
    LLMSolicitud,
    TareaLLM,
)
from app.llm.herramientas import ACTUALIZAR_PERFIL, BUSCAR_FUENTES, BUSCAR_VIDEO, RESPONDER

MODELO_FALSO = "fake-llm"
TOKENS_FALSOS_ENTRADA = 120
TOKENS_FALSOS_SALIDA = 80
AUTORIDAD_MINIMA_CITA = 2
PREGUNTAS_POR_DEFECTO = 5
_PATRON_ID_FUENTE = re.compile(r'id_fuente="([0-9a-f-]{36})"')
_PATRON_TOTAL = re.compile(r"Exactamente (\d+) preguntas")
_PATRON_OBJETO = re.compile(r"\{[^{}]*\}")
_PATRON_MENSAJE = re.compile(r"<mensaje_estudiante>\n(.*?)\n</mensaje_estudiante>", re.DOTALL)

Programada = LLMRespuesta | Exception


def _respuesta(bloques: tuple[Any, ...], razon: str = "end_turn") -> LLMRespuesta:
    return LLMRespuesta(
        bloques=bloques,
        razon_parada=razon,
        modelo=MODELO_FALSO,
        tokens_entrada=TOKENS_FALSOS_ENTRADA,
        tokens_salida=TOKENS_FALSOS_SALIDA,
    )


def respuesta_texto(texto: str) -> LLMRespuesta:
    return _respuesta((BloqueTextoLLM(texto),))


def respuesta_herramienta(nombre: str, entrada: dict[str, Any]) -> LLMRespuesta:
    uso = BloqueUsoHerramienta(id=f"toolu_{uuid.uuid4().hex[:12]}", nombre=nombre, entrada=entrada)
    return _respuesta((uso,), razon="tool_use")


class FakeClient(LLMClient):
    """Determinista y sin red: es el adaptador por defecto en desarrollo y en CI."""

    def __init__(self) -> None:
        self._programadas: deque[Programada] = deque()
        self.solicitudes: list[LLMSolicitud] = []

    def programar(self, *respuestas: Programada) -> None:
        self._programadas.extend(respuestas)

    def completar(self, solicitud: LLMSolicitud) -> LLMRespuesta:
        self.solicitudes.append(solicitud)
        if self._programadas:
            return self._siguiente_programada()
        generadores = {
            TareaLLM.CUESTIONARIO: self._cuestionario,
            TareaLLM.PLAN: self._plan,
            TareaLLM.TUTOR: self._tutor,
            TareaLLM.CONSOLIDACION: self._consolidacion,
        }
        return generadores[solicitud.tarea](solicitud)

    def _siguiente_programada(self) -> LLMRespuesta:
        siguiente = self._programadas.popleft()
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    def _cuestionario(self, solicitud: LLMSolicitud) -> LLMRespuesta:
        texto = solicitud.texto_usuario()
        ids = _PATRON_ID_FUENTE.findall(texto)
        coincidencia = _PATRON_TOTAL.search(texto)
        total = int(coincidencia.group(1)) if coincidencia else PREGUNTAS_POR_DEFECTO
        preguntas = [_pregunta_falsa(i, ids[i % len(ids)] if ids else None) for i in range(total)]
        datos = {"tema_academico": True, "materia": "Ciencias", "preguntas": preguntas}
        return respuesta_texto(json.dumps(datos, ensure_ascii=False))

    def _plan(self, solicitud: LLMSolicitud) -> LLMRespuesta:
        ids = _PATRON_ID_FUENTE.findall(solicitud.texto_usuario())
        return respuesta_texto(json.dumps(plan_falso(ids[:1]), ensure_ascii=False))

    def _consolidacion(self, _: LLMSolicitud) -> LLMRespuesta:
        return respuesta_herramienta(ACTUALIZAR_PERFIL, actualizacion_falsa())

    def _tutor(self, solicitud: LLMSolicitud) -> LLMRespuesta:
        mensaje = _mensaje_estudiante(solicitud).lower()
        usadas = _herramientas_usadas(solicitud)
        if not _es_academico(mensaje):
            return respuesta_herramienta(RESPONDER, {"ambito": _ambito(mensaje), "bloques": []})
        if BUSCAR_FUENTES not in usadas:
            return respuesta_herramienta(BUSCAR_FUENTES, {"consulta": mensaje[:80] or "tema"})
        if "video" in mensaje and BUSCAR_VIDEO not in usadas:
            return respuesta_herramienta(BUSCAR_VIDEO, {"tema": mensaje[:80] or "tema"})
        return respuesta_herramienta(RESPONDER, _respuesta_academica(solicitud, mensaje))


def _pregunta_falsa(indice: int, id_fuente: str | None) -> dict[str, Any]:
    return {
        "enunciado": f"Pregunta diagnóstica {indice + 1} sobre el tema",
        "opciones": {"a": "Opción A", "b": "Opción B", "c": "Opción C", "d": "Opción D"},
        "respuesta_correcta": "a",
        "id_fuente": id_fuente,
    }


def plan_falso(ids_fuentes: list[str]) -> dict[str, Any]:
    return {
        "titulo": "Plan de estudio del tema",
        "explicacion": "Empieza por los conceptos básicos y avanza con ejemplos propios.",
        "tecnicas_estudio": ["Práctica espaciada", "Recuperación activa"],
        "actividades": [
            "Escribe con tus palabras la idea principal del tema.",
            "Construye un mapa conceptual con los conceptos clave.",
            "Explica el tema a un compañero y anota sus preguntas.",
        ],
        "fuentes_usadas": ids_fuentes,
    }


def actualizacion_falsa() -> dict[str, Any]:
    return {
        "resumen_conversacion": "Repasó los conceptos principales con ejemplos.",
        "dificultades": ["Relacionar los conceptos entre sí"],
        "fortalezas": ["Identifica las definiciones clave"],
        "detalle": "MEDIO",
        "ritmo": "MEDIO",
        "resumen_perfil": "Avanza bien con ejemplos concretos y preguntas de comprobación.",
    }


def _mensaje_estudiante(solicitud: LLMSolicitud) -> str:
    textos = [
        b.texto
        for m in solicitud.mensajes
        if m.rol == "user"
        for b in m.contenido
        if isinstance(b, BloqueTextoLLM)
    ]
    coincidencias = [_PATRON_MENSAJE.search(t) for t in textos]
    encontrados = [c.group(1) for c in coincidencias if c]
    return encontrados[-1] if encontrados else ""


def _herramientas_usadas(solicitud: LLMSolicitud) -> set[str]:
    return {
        b.nombre
        for m in _mensajes_del_turno(solicitud)
        for b in m.contenido
        if isinstance(b, BloqueUsoHerramienta)
    }


def _mensajes_del_turno(solicitud: LLMSolicitud) -> list[Any]:
    indices = [
        i
        for i, m in enumerate(solicitud.mensajes)
        if any(
            isinstance(b, BloqueTextoLLM) and "<mensaje_estudiante>" in b.texto for b in m.contenido
        )
    ]
    return list(solicitud.mensajes[indices[-1] :]) if indices else []


def _resultados(solicitud: LLMSolicitud) -> list[dict[str, Any]]:
    contenidos = [
        b.contenido
        for m in _mensajes_del_turno(solicitud)
        for b in m.contenido
        if isinstance(b, BloqueResultadoHerramienta)
    ]
    return [json.loads(o) for c in contenidos for o in _PATRON_OBJETO.findall(c)]


def _es_academico(mensaje: str) -> bool:
    return "futbol" not in mensaje and "hacerme daño" not in mensaje


def _ambito(mensaje: str) -> str:
    return "RIESGO" if "hacerme daño" in mensaje else "NO_ACADEMICO"


def _respuesta_academica(solicitud: LLMSolicitud, mensaje: str) -> dict[str, Any]:
    resultados = _resultados(solicitud)
    citables = [
        r["id_fuente"] for r in resultados if r.get("autoridad", 0) >= AUTORIDAD_MINIMA_CITA
    ]
    videos = [r["id_video"] for r in resultados if "id_video" in r]
    bloques: list[dict[str, Any]] = [_bloque_explicacion(citables[:1])]
    if videos:
        bloques += [
            {"tipo": "video", "id_video": videos[0]},
            {
                "tipo": "pregunta_resumen",
                "enunciado": "Resume con tus palabras el video.",
                "id_video": videos[0],
            },
        ]
    bloques.append({"tipo": "pregunta_comprension", "enunciado": "¿Qué parte quieres repasar?"})
    entrada: dict[str, Any] = {"ambito": "ACADEMICO", "bloques": bloques}
    solicitud_visual = _solicitud_visual(mensaje)
    if solicitud_visual:
        entrada["solicitud_visual"] = solicitud_visual
    return entrada


def _bloque_explicacion(fuentes: list[str]) -> dict[str, Any]:
    if fuentes:
        return {
            "tipo": "texto",
            "contenido": "Según la fuente consultada, este es el concepto central del tema.",
            "afirma_hechos": True,
            "fuentes": fuentes,
        }
    return {"tipo": "texto", "contenido": "No encontré una fuente verificable sobre esto."}


def _solicitud_visual(mensaje: str) -> dict[str, Any] | None:
    if "diagrama" in mensaje:
        return {
            "concepto_canonico": "proceso del tema",
            "tipo_preferido": "DIAGRAMA",
            "descripcion_visual": "Flujo de las etapas del proceso",
            "exige_exactitud": True,
            "diagrama": {
                "tipo_diagrama": "flujo",
                "titulo": "Etapas del proceso",
                "nodos": [{"id": "a", "texto": "Inicio"}, {"id": "b", "texto": "Resultado"}],
                "aristas": [{"desde": "a", "hasta": "b", "etiqueta": "produce"}],
            },
        }
    if "imagen" in mensaje:
        return {
            "concepto_canonico": "celula vegetal",
            "tipo_preferido": "IMAGEN_REAL",
            "descripcion_visual": "Fotografía al microscopio de una célula vegetal",
            "exige_exactitud": False,
        }
    return None
