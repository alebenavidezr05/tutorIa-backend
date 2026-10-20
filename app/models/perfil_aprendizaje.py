import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto.tipos import JsonCifrado
from app.models.tipos import FechaHoraUTC, nuevo_uuid


class PerfilAprendizaje(Base):
    __tablename__ = "perfil_aprendizaje"

    id_perfil: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"), unique=True)
    personalizacion_activa: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_consentimiento: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
    preferencias: Mapped[dict[str, Any]] = mapped_column(
        JsonCifrado("perfil_aprendizaje.preferencias")
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    total_interacciones: Mapped[int] = mapped_column(Integer, default=0)
    fecha_actualizacion: Mapped[datetime] = mapped_column(FechaHoraUTC)
