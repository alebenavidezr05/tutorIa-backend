import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoSuscripcion, PlanSuscripcion
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class Suscripcion(Base):
    __tablename__ = "suscripcion"

    id_suscripcion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"), index=True)
    plan: Mapped[PlanSuscripcion] = mapped_column(tipo_enum(PlanSuscripcion))
    estado: Mapped[EstadoSuscripcion] = mapped_column(tipo_enum(EstadoSuscripcion))
    referencia_pasarela: Mapped[str | None] = mapped_column(String(100), index=True)
    fecha_inicio: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_fin: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
