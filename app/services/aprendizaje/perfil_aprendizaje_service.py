import uuid
from collections.abc import Iterable

from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.exceptions.base import RecursoNoEncontradoError
from app.models.enums import FinalidadConsentimiento, FormatoExplicacion, OtorgadoPor
from app.models.perfil_aprendizaje import PerfilAprendizaje
from app.repositories.conversacion import PerfilAprendizajeRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.auth import ContextoSolicitud
from app.schemas.perfil_aprendizaje import (
    FormatoPublico,
    PerfilAprendizajePublico,
    PreferenciasAprendizaje,
    TemaPublico,
)
from app.services.aprendizaje.actualizador_preferencias import ActualizadorPreferencias
from app.services.aprendizaje.senales_extractor import SenalesMensaje
from app.services.consentimiento_service import ConsentimientoService, Otorgamiento

PUNTAJE_PREFERIDO = 0.6
PUNTAJE_POCO_UTIL = 0.4
CONFIANZA_SUFICIENTE = 0.5
NOMBRE_FORMATO = {
    FormatoExplicacion.EJEMPLO: "con ejemplos",
    FormatoExplicacion.PASO_A_PASO: "paso a paso",
    FormatoExplicacion.VISUAL: "con recursos visuales",
    FormatoExplicacion.ANALOGIA: "con analogías",
    FormatoExplicacion.FORMAL: "con explicaciones formales",
    FormatoExplicacion.TEORIA: "con explicaciones teóricas",
}
NOMBRE_DETALLE = {
    "BREVE": "Prefiere respuestas breves",
    "MEDIO": "Prefiere un nivel de detalle medio",
    "DETALLADO": "Prefiere respuestas detalladas",
}
NOMBRE_RITMO = {
    "LENTO": "Avanza mejor con calma",
    "MEDIO": "Avanza a un ritmo medio",
    "RAPIDO": "Avanza rápido",
}


def etiqueta_formato(formato: FormatoExplicacion, puntaje: float, confianza: float) -> str:
    nombre = NOMBRE_FORMATO[formato]
    if confianza < CONFIANZA_SUFICIENTE:
        return f"Aún no hay suficiente evidencia sobre explicaciones {nombre}"
    if puntaje >= PUNTAJE_PREFERIDO:
        return f"Suele entender mejor {nombre}"
    if puntaje <= PUNTAJE_POCO_UTIL:
        return f"Las explicaciones {nombre} le han servido menos"
    return f"Las explicaciones {nombre} le funcionan de forma variable"


class PerfilAprendizajeService:
    """El estudiante controla su perfil: lo ve en lenguaje claro, lo desactiva y lo reinicia."""

    def __init__(
        self,
        perfiles: PerfilAprendizajeRepository,
        usuarios: UsuarioRepository,
        actualizador: ActualizadorPreferencias,
        consentimientos: ConsentimientoService,
        uow: UnitOfWork,
    ) -> None:
        self._perfiles = perfiles
        self._usuarios = usuarios
        self._actualizador = actualizador
        self._consentimientos = consentimientos
        self._uow = uow

    def obtener(self, id_usuario: uuid.UUID) -> PerfilAprendizajePublico:
        perfil = self.obtener_o_crear(id_usuario)
        self._uow.commit()
        return self._publico(perfil)

    def obtener_o_crear(self, id_usuario: uuid.UUID) -> PerfilAprendizaje:
        perfil = self._perfiles.obtener_por_usuario(id_usuario)
        if perfil is not None:
            return perfil
        return self._perfiles.agregar(
            PerfilAprendizaje(
                id_usuario=id_usuario,
                personalizacion_activa=False,
                preferencias=PreferenciasAprendizaje().model_dump(mode="json"),
                version=1,
                total_interacciones=0,
                fecha_actualizacion=ahora_utc(),
            )
        )

    def activar_personalizacion(
        self, id_usuario: uuid.UUID, activa: bool, contexto: ContextoSolicitud
    ) -> PerfilAprendizajePublico:
        perfil = self.obtener_o_crear(id_usuario)
        perfil.personalizacion_activa = activa
        perfil.fecha_consentimiento = ahora_utc() if activa else perfil.fecha_consentimiento
        self._registrar_consentimiento(id_usuario, activa, contexto)
        self._uow.commit()
        return self._publico(perfil)

    def reiniciar(self, id_usuario: uuid.UUID) -> None:
        perfil = self.obtener_o_crear(id_usuario)
        self.guardar(perfil, PreferenciasAprendizaje())
        perfil.total_interacciones = 0
        perfil.version += 1
        self._uow.commit()

    @staticmethod
    def preferencias(perfil: PerfilAprendizaje) -> PreferenciasAprendizaje:
        return PreferenciasAprendizaje.model_validate(perfil.preferencias)

    @staticmethod
    def guardar(perfil: PerfilAprendizaje, preferencias: PreferenciasAprendizaje) -> None:
        perfil.preferencias = preferencias.model_dump(mode="json")
        perfil.fecha_actualizacion = ahora_utc()

    def registrar_turno(
        self,
        perfil: PerfilAprendizaje,
        senales: SenalesMensaje,
        formatos_previos: Iterable[FormatoExplicacion],
    ) -> None:
        """No confirma: forma parte de la transacción del turno."""
        actualizadas = self._actualizador.aplicar_senales(
            self.preferencias(perfil), senales, formatos_previos
        )
        self.guardar(perfil, actualizadas)
        perfil.total_interacciones += 1

    def registrar_feedback(
        self, perfil: PerfilAprendizaje, util: bool, formatos: Iterable[FormatoExplicacion]
    ) -> None:
        self.guardar(
            perfil, self._actualizador.aplicar_feedback(self.preferencias(perfil), util, formatos)
        )

    def _registrar_consentimiento(
        self, id_usuario: uuid.UUID, activa: bool, contexto: ContextoSolicitud
    ) -> None:
        usuario = self._usuarios.obtener_por_id(id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        self._consentimientos.registrar(
            id_usuario,
            usuario.correo_hash,
            Otorgamiento(FinalidadConsentimiento.PERSONALIZACION, activa),
            OtorgadoPor.TITULAR,
            contexto,
        )

    def _publico(self, perfil: PerfilAprendizaje) -> PerfilAprendizajePublico:
        prefs = self.preferencias(perfil)
        formatos = [
            FormatoPublico(
                formato=f,
                puntaje=prefs.formatos.de(f).puntaje,
                confianza=prefs.formatos.de(f).confianza,
                etiqueta_legible=etiqueta_formato(
                    f, prefs.formatos.de(f).puntaje, prefs.formatos.de(f).confianza
                ),
            )
            for f in FormatoExplicacion
        ]
        return PerfilAprendizajePublico(
            personalizacion_activa=perfil.personalizacion_activa,
            total_interacciones=perfil.total_interacciones,
            resumen=prefs.resumen,
            formatos=formatos,
            detalle=NOMBRE_DETALLE[prefs.detalle.value],
            ritmo=NOMBRE_RITMO[prefs.ritmo.value],
            temas=[
                TemaPublico(tema=t, dificultades=d.dificultades, fortalezas=d.fortalezas)
                for t, d in prefs.temas.items()
            ],
        )
