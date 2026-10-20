import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.crypto.tipos import JsonCifrado, TextoCifrado
from app.models.enums import AmbitoMensaje, IntencionMensaje, MotivoFeedback, RolMensaje
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum

if TYPE_CHECKING:
    from app.models.conversacion import Conversacion


class Mensaje(Base):
    __tablename__ = "mensaje"
    __table_args__ = (
        UniqueConstraint("id_conversacion", "orden"),
        Index("ix_mensaje_conversacion_orden", "id_conversacion", "orden"),
    )

    id_mensaje: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_conversacion: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversacion.id_conversacion", ondelete="CASCADE")
    )
    orden: Mapped[int] = mapped_column(Integer)
    rol: Mapped[RolMensaje] = mapped_column(tipo_enum(RolMensaje))
    contenido: Mapped[str] = mapped_column(TextoCifrado("mensaje.contenido"))
    bloques: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonCifrado("mensaje.bloques"))
    ambito: Mapped[AmbitoMensaje | None] = mapped_column(tipo_enum(AmbitoMensaje))
    formatos_usados: Mapped[list[str] | None] = mapped_column(JSON)
    intencion: Mapped[IntencionMensaje | None] = mapped_column(tipo_enum(IntencionMensaje))
    util: Mapped[bool | None] = mapped_column(Boolean)
    motivo_feedback: Mapped[MotivoFeedback | None] = mapped_column(tipo_enum(MotivoFeedback))
    validado: Mapped[bool | None] = mapped_column(Boolean)
    modelo: Mapped[str | None] = mapped_column(String(60))
    tokens_entrada: Mapped[int | None] = mapped_column(Integer)
    tokens_salida: Mapped[int | None] = mapped_column(Integer)
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    fecha: Mapped[datetime] = mapped_column(FechaHoraUTC)

    conversacion: Mapped["Conversacion"] = relationship()
