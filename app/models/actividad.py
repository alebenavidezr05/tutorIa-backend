import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, SmallInteger, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.crypto.tipos import TextoCifrado
from app.models.enums import EstadoActividad
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum

if TYPE_CHECKING:
    from app.models.plan_estudio import PlanEstudio


class Actividad(Base):
    __tablename__ = "actividad"

    id_actividad: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_plan: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_estudio.id_plan", ondelete="CASCADE")
    )
    numero_orden: Mapped[int] = mapped_column(SmallInteger)
    enunciado: Mapped[str] = mapped_column(Text)
    respuesta_usuario: Mapped[str | None] = mapped_column(
        TextoCifrado("actividad.respuesta_usuario")
    )
    estado: Mapped[EstadoActividad] = mapped_column(
        tipo_enum(EstadoActividad), default=EstadoActividad.PENDIENTE
    )
    fecha_completado: Mapped[datetime | None] = mapped_column(FechaHoraUTC)

    plan: Mapped["PlanEstudio"] = relationship(back_populates="actividades")
