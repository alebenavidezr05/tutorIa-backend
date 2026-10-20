import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import OperacionIA, ProveedorIA
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class ConsumoIA(Base):
    __tablename__ = "consumo_ia"
    __table_args__ = (
        Index("ix_consumo_ia_fecha", "fecha"),
        Index("ix_consumo_ia_usuario_fecha", "id_usuario", "fecha"),
    )

    id_consumo: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="SET NULL")
    )
    proveedor: Mapped[ProveedorIA] = mapped_column(tipo_enum(ProveedorIA))
    modelo: Mapped[str] = mapped_column(String(60))
    operacion: Mapped[OperacionIA] = mapped_column(tipo_enum(OperacionIA))
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0)
    tokens_cache_lectura: Mapped[int] = mapped_column(Integer, default=0)
    tokens_cache_escritura: Mapped[int] = mapped_column(Integer, default=0)
    imagenes: Mapped[int] = mapped_column(SmallInteger, default=0)
    costo_estimado_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6))
    es_estimacion: Mapped[bool] = mapped_column(Boolean)
    exito: Mapped[bool] = mapped_column(Boolean)
    fecha: Mapped[datetime] = mapped_column(FechaHoraUTC)
