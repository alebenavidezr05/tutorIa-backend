from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.tipos import FechaHoraUTC


class LimiteFrecuencia(Base):
    """Contador de intentos por clave (HMAC de IP o correo) para frenar fuerza bruta sin Redis."""

    __tablename__ = "limite_frecuencia"

    clave_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    ventana_inicio: Mapped[datetime] = mapped_column(FechaHoraUTC)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
