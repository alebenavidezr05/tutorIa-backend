import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.tipos import nuevo_uuid


class UsoDiario(Base):
    __tablename__ = "uso_diario"
    __table_args__ = (UniqueConstraint("id_usuario", "fecha"),)

    id_uso: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"))
    fecha: Mapped[date] = mapped_column(Date)
    mensajes: Mapped[int] = mapped_column(Integer, default=0)
    planes: Mapped[int] = mapped_column(Integer, default=0)
    imagenes_ia: Mapped[int] = mapped_column(Integer, default=0)
    busquedas_video: Mapped[int] = mapped_column(Integer, default=0)
    archivos: Mapped[int] = mapped_column(Integer, default=0)
