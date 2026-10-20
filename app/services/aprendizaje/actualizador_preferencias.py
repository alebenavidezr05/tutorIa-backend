"""Actualización determinista del perfil en cada turno (§13.3, paso 1). Clase pura."""

from collections.abc import Iterable

from app.models.enums import FormatoExplicacion, IntencionMensaje, NivelDetalle, TipoEvento
from app.schemas.perfil_aprendizaje import (
    EstiloPregunta,
    EvidenciaFormato,
    FormatosPerfil,
    PreferenciasAprendizaje,
)
from app.services.aprendizaje.senales_extractor import SenalesMensaje

SENAL_POSITIVA = 1.0
SENAL_NEGATIVA = 0.0
DETALLE_POR_EVENTO = {
    TipoEvento.PIDE_SIMPLIFICAR: NivelDetalle.BREVE,
    TipoEvento.PIDE_RESUMEN: NivelDetalle.BREVE,
    TipoEvento.PIDE_MAS_DETALLE: NivelDetalle.DETALLADO,
}


class ActualizadorPreferencias:
    """Media móvil exponencial: puntaje ← puntaje + α·(señal − puntaje).
    La confianza crece con las observaciones: el perfil es una hipótesis, no una etiqueta."""

    def __init__(self, alpha: float, observaciones_confianza: int) -> None:
        self._alpha = alpha
        self._observaciones_confianza = observaciones_confianza

    def aplicar_senales(
        self,
        preferencias: PreferenciasAprendizaje,
        senales: SenalesMensaje,
        formatos_previos: Iterable[FormatoExplicacion],
    ) -> PreferenciasAprendizaje:
        formatos = preferencias.formatos
        for formato in senales.formatos_pedidos:
            formatos = self._observar(formatos, formato, SENAL_POSITIVA)
        if TipoEvento.NO_ENTENDIO in senales.eventos:
            for formato in formatos_previos:
                formatos = self._observar(formatos, formato, SENAL_NEGATIVA)
        return preferencias.model_copy(
            update={
                "formatos": formatos,
                "detalle": self._detalle(preferencias.detalle, senales),
                "estilo_pregunta": self._estilo(preferencias.estilo_pregunta, senales),
            }
        )

    def aplicar_feedback(
        self,
        preferencias: PreferenciasAprendizaje,
        util: bool,
        formatos: Iterable[FormatoExplicacion],
    ) -> PreferenciasAprendizaje:
        senal = SENAL_POSITIVA if util else SENAL_NEGATIVA
        actualizados = preferencias.formatos
        for formato in formatos:
            actualizados = self._observar(actualizados, formato, senal)
        return preferencias.model_copy(update={"formatos": actualizados})

    def _observar(
        self, formatos: FormatosPerfil, formato: FormatoExplicacion, senal: float
    ) -> FormatosPerfil:
        actual = formatos.de(formato)
        observaciones = actual.observaciones + 1
        nueva = EvidenciaFormato(
            puntaje=round(actual.puntaje + self._alpha * (senal - actual.puntaje), 4),
            confianza=round(min(1.0, observaciones / self._observaciones_confianza), 4),
            observaciones=observaciones,
        )
        return formatos.model_copy(update={formato.value.lower(): nueva})

    @staticmethod
    def _detalle(actual: NivelDetalle, senales: SenalesMensaje) -> NivelDetalle:
        pedidos = [DETALLE_POR_EVENTO[e] for e in senales.eventos if e in DETALLE_POR_EVENTO]
        return pedidos[-1] if pedidos else actual

    def _estilo(self, estilo: EstiloPregunta, senales: SenalesMensaje) -> EstiloPregunta:
        return EstiloPregunta(
            longitud_media_palabras=round(
                self._media(estilo.longitud_media_palabras, senales.longitud_palabras), 2
            ),
            pide_respuesta_directa=round(
                self._media(
                    estilo.pide_respuesta_directa,
                    float(senales.intencion == IntencionMensaje.RESOLVER_TAREA),
                ),
                4,
            ),
            repregunta=round(self._media(estilo.repregunta, float(senales.repite_pregunta)), 4),
            vocabulario_tecnico=round(
                self._media(estilo.vocabulario_tecnico, float(senales.usa_vocabulario_tecnico)), 4
            ),
        )

    def _media(self, actual: float, observado: float) -> float:
        return actual + self._alpha * (observado - actual)
