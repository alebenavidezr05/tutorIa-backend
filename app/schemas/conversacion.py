import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    AmbitoMensaje,
    CategoriaAlerta,
    EstadoConversacion,
    MotivoFeedback,
    NivelCognitivo,
    RolMensaje,
)
from app.schemas.archivo import ArchivoPublico
from app.schemas.fuente import FuentePublica, ReferenciaPublica
from app.schemas.visual import VisualPublico
from app.validators.tema import validar_tema

MAX_CONTENIDO_MENSAJE = 4000
MAX_COMENTARIO_REPORTE = 500


class IniciarConversacionEntrada(BaseModel):
    tema: str | None = Field(default=None, max_length=400)
    id_plan: uuid.UUID | None = None

    @field_validator("tema")
    @classmethod
    def _tema(cls, valor: str | None) -> str | None:
        return validar_tema(valor) if valor is not None else None


class ConversacionPublica(BaseModel):
    id_conversacion: uuid.UUID
    tema: str
    estado: EstadoConversacion
    nivel_cognitivo: NivelCognitivo
    id_plan: uuid.UUID | None
    acepta_archivos: bool
    fecha_inicio: datetime
    fecha_ultimo_mensaje: datetime


class ConversacionesPagina(BaseModel):
    items: list[ConversacionPublica]
    total: int
    pagina: int
    tamano: int


class MensajePublico(BaseModel):
    id_mensaje: uuid.UUID
    rol: RolMensaje
    contenido: str
    bloques: list[dict[str, Any]] | None
    fuentes: list[FuentePublica]
    visual: VisualPublico | None
    archivo: ArchivoPublico | None
    util: bool | None
    fecha: datetime


class ConversacionDetalle(ConversacionPublica):
    mensajes: list[MensajePublico]


class EnviarMensajeEntrada(BaseModel):
    # La longitud real (1–1500) la valida `validar_mensaje_chat` en el service tras normalizar.
    contenido: str = Field(min_length=1, max_length=MAX_CONTENIDO_MENSAJE)
    id_archivo: uuid.UUID | None = None


class MensajeTutorPublico(BaseModel):
    id_mensaje: uuid.UUID
    ambito: AmbitoMensaje
    bloques: list[dict[str, Any]]
    fuentes: list[FuentePublica]
    visual: VisualPublico | None
    formatos_usados: list[str]
    validado: bool
    fecha: datetime


class ResumenSesion(BaseModel):
    resumen: str
    referencias: list[ReferenciaPublica]
    aviso: str


class FeedbackEntrada(BaseModel):
    util: bool
    motivo: MotivoFeedback | None = None


class ReporteEntrada(BaseModel):
    categoria: CategoriaAlerta
    comentario: str | None = Field(default=None, max_length=MAX_COMENTARIO_REPORTE)
