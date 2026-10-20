import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import TipoEvento
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class EventoAprendizaje(Base):
    __tablename__ = "evento_aprendizaje"
    __table_args__ = (Index("ix_evento_aprendizaje_usuario_fecha", "id_usuario", "fecha"),)

    id_evento: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"))
    # Nulo solo para eventos que no nacen en el chat (ACTIVIDAD_COMPLETADA).
    id_conversacion: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversacion.id_conversacion", ondelete="CASCADE")
    )
    id_mensaje: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mensaje.id_mensaje", ondelete="CASCADE")
    )
    tipo: Mapped[TipoEvento] = mapped_column(tipo_enum(TipoEvento))
    valor: Mapped[float | None] = mapped_column(Float)
    fecha: Mapped[datetime] = mapped_column(FechaHoraUTC)
