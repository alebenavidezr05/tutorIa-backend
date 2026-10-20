import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto.tipos import TextoCifrado
from app.models.enums import EstadoSolicitud, TipoSolicitud
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class SolicitudTitular(Base):
    __tablename__ = "solicitud_titular"

    id_solicitud: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="SET NULL"), index=True
    )
    tipo: Mapped[TipoSolicitud] = mapped_column(tipo_enum(TipoSolicitud))
    detalle: Mapped[str] = mapped_column(TextoCifrado("solicitud_titular.detalle"))
    estado: Mapped[EstadoSolicitud] = mapped_column(
        tipo_enum(EstadoSolicitud), default=EstadoSolicitud.RECIBIDA
    )
    fecha_recepcion: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_limite: Mapped[date] = mapped_column(Date)
    fecha_respuesta: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
    respuesta: Mapped[str | None] = mapped_column(TextoCifrado("solicitud_titular.respuesta"))
