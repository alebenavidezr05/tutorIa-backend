import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto.tipos import TextoCifrado
from app.models.enums import EstadoConversacion, NivelCognitivo
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class Conversacion(Base):
    __tablename__ = "conversacion"
    __table_args__ = (
        Index("ix_conversacion_usuario_ultimo", "id_usuario", "fecha_ultimo_mensaje"),
    )

    id_conversacion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"))
    id_plan: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plan_estudio.id_plan", ondelete="SET NULL")
    )
    tema: Mapped[str] = mapped_column(TextoCifrado("conversacion.tema"))
    nivel_cognitivo: Mapped[NivelCognitivo] = mapped_column(tipo_enum(NivelCognitivo))
    estado: Mapped[EstadoConversacion] = mapped_column(
        tipo_enum(EstadoConversacion), default=EstadoConversacion.ABIERTA
    )
    consolidada: Mapped[bool] = mapped_column(Boolean, default=False)
    resumen: Mapped[str | None] = mapped_column(TextoCifrado("conversacion.resumen"))
    fecha_inicio: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_ultimo_mensaje: Mapped[datetime] = mapped_column(FechaHoraUTC)
