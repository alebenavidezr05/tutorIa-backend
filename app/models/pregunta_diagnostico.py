import uuid

from sqlalchemy import Boolean, ForeignKey, SmallInteger, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import OpcionRespuesta
from app.models.tipos import nuevo_uuid, tipo_enum


class PreguntaDiagnostico(Base):
    __tablename__ = "pregunta_diagnostico"
    __table_args__ = (UniqueConstraint("id_sesion", "orden"),)

    id_pregunta: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_sesion: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sesion_diagnostico.id_sesion", ondelete="CASCADE")
    )
    enunciado: Mapped[str] = mapped_column(Text)
    opcion_a: Mapped[str] = mapped_column(Text)
    opcion_b: Mapped[str] = mapped_column(Text)
    opcion_c: Mapped[str] = mapped_column(Text)
    opcion_d: Mapped[str] = mapped_column(Text)
    respuesta_correcta: Mapped[OpcionRespuesta] = mapped_column(tipo_enum(OpcionRespuesta))
    id_fuente: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fuente.id_fuente"))
    respuesta_usuario: Mapped[OpcionRespuesta | None] = mapped_column(tipo_enum(OpcionRespuesta))
    es_correcta: Mapped[bool | None] = mapped_column(Boolean)
    orden: Mapped[int] = mapped_column(SmallInteger)
