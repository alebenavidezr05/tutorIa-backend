import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto.tipos import TextoCifrado
from app.models.enums import CategoriaAlerta, EstadoAlerta, OrigenAlerta
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class AlertaSeguridad(Base):
    __tablename__ = "alerta_seguridad"
    __table_args__ = (Index("ix_alerta_seguridad_estado_fecha", "estado", "fecha"),)

    id_alerta: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"))
    id_mensaje: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mensaje.id_mensaje", ondelete="SET NULL")
    )
    origen: Mapped[OrigenAlerta] = mapped_column(tipo_enum(OrigenAlerta))
    categoria: Mapped[CategoriaAlerta] = mapped_column(tipo_enum(CategoriaAlerta))
    estado: Mapped[EstadoAlerta] = mapped_column(
        tipo_enum(EstadoAlerta), default=EstadoAlerta.ABIERTA
    )
    detalle: Mapped[str | None] = mapped_column(TextoCifrado("alerta_seguridad.detalle"))
    fecha: Mapped[datetime] = mapped_column(FechaHoraUTC)
