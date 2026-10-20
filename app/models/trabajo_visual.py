import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoTrabajoVisual, TipoVisualPreferido
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class TrabajoVisual(Base):
    __tablename__ = "trabajo_visual"

    id_trabajo: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_mensaje: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mensaje.id_mensaje", ondelete="CASCADE"), unique=True
    )
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"))
    estado: Mapped[EstadoTrabajoVisual] = mapped_column(tipo_enum(EstadoTrabajoVisual))
    concepto_canonico: Mapped[str] = mapped_column(String(100))
    tipo_preferido: Mapped[TipoVisualPreferido] = mapped_column(tipo_enum(TipoVisualPreferido))
    descripcion_visual: Mapped[str] = mapped_column(String(300))
    exige_exactitud: Mapped[bool] = mapped_column(Boolean)
    datos_diagrama: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    id_recurso: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recurso_visual.id_recurso"))
    intentos: Mapped[int] = mapped_column(SmallInteger, default=0)
    codigo_error: Mapped[str | None] = mapped_column(String(50))
    fecha_creacion: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_inicio: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
    fecha_fin: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
