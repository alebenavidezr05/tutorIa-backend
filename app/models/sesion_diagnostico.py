import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.crypto.tipos import TextoCifrado
from app.models.enums import NivelCognitivo
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum

if TYPE_CHECKING:
    from app.models.pregunta_diagnostico import PreguntaDiagnostico


class SesionDiagnostico(Base):
    __tablename__ = "sesion_diagnostico"
    __table_args__ = (Index("ix_sesion_diagnostico_usuario_fecha", "id_usuario", "fecha_creacion"),)

    id_sesion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"))
    tema: Mapped[str] = mapped_column(TextoCifrado("sesion_diagnostico.tema"))
    materia: Mapped[str] = mapped_column(String(100))
    nivel_estimado: Mapped[NivelCognitivo | None] = mapped_column(tipo_enum(NivelCognitivo))
    puntaje_diagnostico: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    total_preguntas: Mapped[int] = mapped_column(SmallInteger)
    fecha_creacion: Mapped[datetime] = mapped_column(FechaHoraUTC)

    preguntas: Mapped[list["PreguntaDiagnostico"]] = relationship(
        order_by="PreguntaDiagnostico.orden",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
