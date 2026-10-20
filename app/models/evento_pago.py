import uuid
from datetime import datetime

from sqlalchemy import String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.tipos import FechaHoraUTC, nuevo_uuid


class EventoPago(Base):
    __tablename__ = "evento_pago"
    __table_args__ = (UniqueConstraint("proveedor", "id_evento_externo"),)

    id_evento_pago: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    proveedor: Mapped[str] = mapped_column(String(40))
    id_evento_externo: Mapped[str] = mapped_column(String(100))
    tipo: Mapped[str] = mapped_column(String(60))
    fecha: Mapped[datetime] = mapped_column(FechaHoraUTC)
