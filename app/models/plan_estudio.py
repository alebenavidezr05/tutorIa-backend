import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EstadoPlan, NivelCognitivo
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum

if TYPE_CHECKING:
    from app.models.actividad import Actividad
    from app.models.sesion_diagnostico import SesionDiagnostico


class PlanEstudio(Base):
    __tablename__ = "plan_estudio"
    __table_args__ = (Index("ix_plan_estudio_usuario_fecha", "id_usuario", "fecha_generacion"),)

    id_plan: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_sesion: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sesion_diagnostico.id_sesion", ondelete="CASCADE")
    )
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"))
    titulo: Mapped[str] = mapped_column(String(200))
    explicacion: Mapped[str] = mapped_column(Text)
    tecnicas_estudio: Mapped[list[str]] = mapped_column(JSON)
    nivel_bloom: Mapped[NivelCognitivo] = mapped_column(tipo_enum(NivelCognitivo))
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0)
    validado: Mapped[bool] = mapped_column(Boolean)
    estado: Mapped[EstadoPlan] = mapped_column(tipo_enum(EstadoPlan), default=EstadoPlan.GENERADO)
    fecha_generacion: Mapped[datetime] = mapped_column(FechaHoraUTC)

    actividades: Mapped[list["Actividad"]] = relationship(
        order_by="Actividad.numero_orden",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="plan",
    )
    sesion: Mapped["SesionDiagnostico"] = relationship()
