from dataclasses import dataclass

from app.llm.politica_nivel import politica_de
from app.llm.prompts import DESCRIPCION_GRUPO_EDAD
from app.llm.prompts_tutor import INSTRUCCION_EXPLORACION, ContextoTurno
from app.models.conversacion import Conversacion
from app.models.enums import FormatoExplicacion
from app.models.plan_estudio import PlanEstudio
from app.models.sesion_diagnostico import SesionDiagnostico
from app.models.video_curado import VideoCurado
from app.schemas.perfil_aprendizaje import PreferenciasAprendizaje, TemaPerfil
from app.services.estudiante import PerfilEstudiante
from app.validators.perfil import normalizar_tema

PUNTAJE_PREFERIDO = 0.6
CONFIANZA_MINIMA = 0.5
LONGITUD_MIN_PALABRA_RELACION = 5


@dataclass(frozen=True)
class DatosContexto:
    conversacion: Conversacion
    estudiante: PerfilEstudiante
    preferencias: PreferenciasAprendizaje | None
    sesion: SesionDiagnostico | None
    plan: PlanEstudio | None
    video_activo: VideoCurado | None
    numero_turno: int
    modo_guia: bool


class ContextoEstudianteBuilder:
    def __init__(self, exploracion_cada: int) -> None:
        self._exploracion_cada = exploracion_cada

    def construir(self, datos: DatosContexto) -> ContextoTurno:
        return ContextoTurno(
            contexto_academico=self._academico(datos),
            grupo_edad=DESCRIPCION_GRUPO_EDAD[datos.estudiante.grupo_edad],
            politica_nivel=self._politica(datos),
            perfil_estudiante=self._perfil(datos) if datos.preferencias is not None else None,
            resumen_conversacion=datos.conversacion.resumen,
            video_activo=self._video(datos.video_activo),
            modo_guia=datos.modo_guia,
        )

    @staticmethod
    def _academico(datos: DatosContexto) -> str:
        lineas = [
            f"Tema: {datos.conversacion.tema}",
            f"Nivel cognitivo: {datos.conversacion.nivel_cognitivo.value}",
            f"Estudiante de {datos.estudiante.tipo_nivel.value}, nivel {datos.estudiante.nivel_educativo}",
        ]
        if datos.sesion is not None:
            falladas = [p.enunciado for p in datos.sesion.preguntas if p.es_correcta is False]
            lineas += [f"Pregunta fallada en el diagnóstico: {e}" for e in falladas]
        if datos.plan is not None:
            lineas.append(f"Plan de estudio: {datos.plan.titulo}")
        return "\n".join(lineas)

    @staticmethod
    def _politica(datos: DatosContexto) -> str:
        politica = politica_de(datos.conversacion.nivel_cognitivo)
        return (
            f"{politica.nivel.value} ({politica.procesos_bloom}). {politica.instrucciones} "
            f"Tipos de pregunta sugeridos: {', '.join(politica.tipos_pregunta)}."
        )

    def _perfil(self, datos: DatosContexto) -> str:
        prefs = datos.preferencias
        assert prefs is not None
        preferidos = [
            f.value.lower()
            for f in FormatoExplicacion
            if prefs.formatos.de(f).puntaje >= PUNTAJE_PREFERIDO
            and prefs.formatos.de(f).confianza >= CONFIANZA_MINIMA
        ]
        estilo = prefs.estilo_pregunta
        lineas = [
            f"Resumen: {prefs.resumen or 'sin resumen todavía'}",
            f"Formatos preferidos: {', '.join(preferidos) or 'aún sin evidencia suficiente'}",
            f"Nivel de detalle: {prefs.detalle.value}; ritmo: {prefs.ritmo.value}",
            f"Estilo de pregunta: {estilo.longitud_media_palabras:.0f} palabras en promedio; "
            f"pide respuesta directa {estilo.pide_respuesta_directa:.2f}; "
            f"repregunta {estilo.repregunta:.2f}; vocabulario técnico {estilo.vocabulario_tecnico:.2f}",
            *self._temas(prefs, datos.conversacion.tema),
        ]
        if datos.numero_turno % self._exploracion_cada == 0:
            lineas.append(INSTRUCCION_EXPLORACION)
        return "\n".join(lineas)

    @staticmethod
    def _temas(prefs: PreferenciasAprendizaje, tema_actual: str) -> list[str]:
        actual = normalizar_tema(tema_actual)
        palabras = {p for p in actual.split() if len(p) >= LONGITUD_MIN_PALABRA_RELACION}
        relacionados: dict[str, TemaPerfil] = {
            clave: datos
            for clave, datos in prefs.temas.items()
            if clave == actual or palabras & set(clave.split())
        }
        return [
            f"Tema {clave}: dificultades {'; '.join(d.dificultades) or 'ninguna'}; "
            f"fortalezas {'; '.join(d.fortalezas) or 'ninguna'}"
            for clave, d in relacionados.items()
        ]

    @staticmethod
    def _video(video: VideoCurado | None) -> str | None:
        if video is None:
            return None
        puntos = "; ".join(video.puntos_clave or []) or "sin puntos clave revisados"
        return f"Video: {video.titulo} ({video.canal}). Puntos clave: {puntos}"
