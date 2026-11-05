import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto.tipos import TextoCifrado
from app.models.enums import EstadoAutorizacion
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class AutorizacionAcudiente(Base):
    __tablename__ = "autorizacion_acudiente"

    id_autorizacion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    correo_acudiente: Mapped[str] = mapped_column(
        TextoCifrado("autorizacion_acudiente.correo_acudiente")
    )
    correo_acudiente_hash: Mapped[str] = mapped_column(String(64), index=True)
    correo_estudiante: Mapped[str] = mapped_column(
        TextoCifrado("autorizacion_acudiente.correo_estudiante")
    )
    correo_estudiante_hash: Mapped[str] = mapped_column(String(64), index=True)
    estado: Mapped[EstadoAutorizacion] = mapped_column(tipo_enum(EstadoAutorizacion))
    permite_compras: Mapped[bool] = mapped_column(Boolean, default=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    version_texto: Mapped[str] = mapped_column(String(20))
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    fecha_solicitud: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_expiracion_token: Mapped[datetime] = mapped_column(FechaHoraUTC)
    # Fecha en que el acudiente respondió desde el enlace (AUTORIZADA o RECHAZADA).
    fecha_verificacion: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
    fecha_revocacion: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
