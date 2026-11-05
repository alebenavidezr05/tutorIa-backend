import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.tipos import FechaHoraUTC, nuevo_uuid


class VerificacionCorreo(Base):
    """Token de un solo uso para confirmar que el correo es de quien se registra. Solo se guarda
    su SHA-256; `correo_hash` (HMAC) permite aplicar el tope de envíos por dirección."""

    __tablename__ = "verificacion_correo"

    id_verificacion: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"), index=True
    )
    correo_hash: Mapped[str] = mapped_column(String(64), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    fecha_creacion: Mapped[datetime] = mapped_column(FechaHoraUTC)
    # Reenviar invalida los tokens anteriores adelantando su expiración a «ahora».
    fecha_expiracion: Mapped[datetime] = mapped_column(FechaHoraUTC)
    usado: Mapped[bool] = mapped_column(Boolean, default=False)
