import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import CategoriaFuente, TipoFuente
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class Fuente(Base):
    __tablename__ = "fuente"

    id_fuente: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    tipo: Mapped[TipoFuente] = mapped_column(tipo_enum(TipoFuente), default=TipoFuente.TEXTO)
    titulo: Mapped[str] = mapped_column(String(300))
    autor: Mapped[str | None] = mapped_column(String(200))
    sitio: Mapped[str] = mapped_column(String(100))
    url: Mapped[str] = mapped_column(String(500))
    url_hash: Mapped[str] = mapped_column(String(64), unique=True)
    fecha_publicacion: Mapped[date | None] = mapped_column(Date)
    fecha_consulta: Mapped[datetime] = mapped_column(FechaHoraUTC)
    licencia: Mapped[str | None] = mapped_column(String(60))
    extracto: Mapped[str | None] = mapped_column(String(1500))
    categoria: Mapped[CategoriaFuente] = mapped_column(tipo_enum(CategoriaFuente))
    autoridad: Mapped[int] = mapped_column(SmallInteger)
    proveedor: Mapped[str] = mapped_column(String(40))
    doi: Mapped[str | None] = mapped_column(String(100), index=True)
    revisada_por_pares: Mapped[bool | None] = mapped_column(Boolean)
    idioma: Mapped[str] = mapped_column(String(2))
    fecha_expiracion: Mapped[datetime] = mapped_column(FechaHoraUTC)


class MensajeFuente(Base):
    __tablename__ = "mensaje_fuente"

    id_mensaje: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mensaje.id_mensaje", ondelete="CASCADE"), primary_key=True
    )
    id_fuente: Mapped[uuid.UUID] = mapped_column(ForeignKey("fuente.id_fuente"), primary_key=True)


class PlanFuente(Base):
    __tablename__ = "plan_fuente"

    id_plan: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plan_estudio.id_plan", ondelete="CASCADE"), primary_key=True
    )
    id_fuente: Mapped[uuid.UUID] = mapped_column(ForeignKey("fuente.id_fuente"), primary_key=True)
