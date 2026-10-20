from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import FormatoExplicacion, NivelDetalle, Ritmo

PUNTAJE_NEUTRO = 0.5
MAX_TEMAS = 30
MAX_ITEMS_TEMA = 5
MAX_TEXTO_ITEM = 120
MAX_CLAVE_TEMA = 100
MAX_RESUMEN = 600


class _Cerrado(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenciaFormato(_Cerrado):
    puntaje: float = Field(default=PUNTAJE_NEUTRO, ge=0, le=1)
    confianza: float = Field(default=0.0, ge=0, le=1)
    observaciones: int = Field(default=0, ge=0)


class FormatosPerfil(_Cerrado):
    ejemplo: EvidenciaFormato = Field(default_factory=EvidenciaFormato)
    paso_a_paso: EvidenciaFormato = Field(default_factory=EvidenciaFormato)
    visual: EvidenciaFormato = Field(default_factory=EvidenciaFormato)
    analogia: EvidenciaFormato = Field(default_factory=EvidenciaFormato)
    formal: EvidenciaFormato = Field(default_factory=EvidenciaFormato)
    teoria: EvidenciaFormato = Field(default_factory=EvidenciaFormato)

    def de(self, formato: FormatoExplicacion) -> EvidenciaFormato:
        evidencia: EvidenciaFormato = getattr(self, formato.value.lower())
        return evidencia


class EstiloPregunta(_Cerrado):
    longitud_media_palabras: float = Field(default=0.0, ge=0)
    pide_respuesta_directa: float = Field(default=0.0, ge=0, le=1)
    repregunta: float = Field(default=0.0, ge=0, le=1)
    vocabulario_tecnico: float = Field(default=0.0, ge=0, le=1)


class TemaPerfil(_Cerrado):
    dificultades: list[str] = Field(default_factory=list, max_length=MAX_ITEMS_TEMA)
    fortalezas: list[str] = Field(default_factory=list, max_length=MAX_ITEMS_TEMA)
    ultima_vez: datetime

    @field_validator("dificultades", "fortalezas")
    @classmethod
    def _longitud_items(cls, valores: list[str]) -> list[str]:
        if any(len(v) > MAX_TEXTO_ITEM for v in valores):
            raise ValueError(f"cada elemento admite hasta {MAX_TEXTO_ITEM} caracteres")
        return valores


class PreferenciasAprendizaje(_Cerrado):
    """Esquema cerrado del perfil (§13.2): solo información pedagógica, nunca datos sensibles."""

    formatos: FormatosPerfil = Field(default_factory=FormatosPerfil)
    detalle: NivelDetalle = NivelDetalle.MEDIO
    ritmo: Ritmo = Ritmo.MEDIO
    estilo_pregunta: EstiloPregunta = Field(default_factory=EstiloPregunta)
    temas: dict[str, TemaPerfil] = Field(default_factory=dict)
    resumen: str = Field(default="", max_length=MAX_RESUMEN)

    @field_validator("temas")
    @classmethod
    def _tope_temas(cls, temas: dict[str, TemaPerfil]) -> dict[str, TemaPerfil]:
        if len(temas) > MAX_TEMAS or any(len(clave) > MAX_CLAVE_TEMA for clave in temas):
            raise ValueError(f"se admiten hasta {MAX_TEMAS} temas")
        return temas


class FormatoPublico(BaseModel):
    formato: FormatoExplicacion
    puntaje: float
    confianza: float
    etiqueta_legible: str


class TemaPublico(BaseModel):
    tema: str
    dificultades: list[str]
    fortalezas: list[str]


class PerfilAprendizajePublico(BaseModel):
    personalizacion_activa: bool
    total_interacciones: int
    resumen: str
    formatos: list[FormatoPublico]
    detalle: str
    ritmo: str
    temas: list[TemaPublico]


class CambioPersonalizacion(BaseModel):
    activa: bool
