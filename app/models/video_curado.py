import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import EstadoVideo
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class VideoCurado(Base):
    __tablename__ = "video_curado"

    id_video: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    youtube_id: Mapped[str] = mapped_column(String(11), unique=True)
    tema_clave: Mapped[str] = mapped_column(String(100), index=True)
    titulo: Mapped[str] = mapped_column(String(300))
    canal: Mapped[str] = mapped_column(String(200))
    id_canal: Mapped[str] = mapped_column(String(40))
    duracion_segundos: Mapped[int] = mapped_column(Integer)
    idioma: Mapped[str] = mapped_column(String(5))
    es_para_ninos: Mapped[bool] = mapped_column(Boolean)
    estado: Mapped[EstadoVideo] = mapped_column(tipo_enum(EstadoVideo))
    puntos_clave: Mapped[list[str] | None] = mapped_column(JSON)
    referencias_revision: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    revisado_por: Mapped[str | None] = mapped_column(String(100))
    fecha_revision: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
    fecha_metadatos: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_creacion: Mapped[datetime] = mapped_column(FechaHoraUTC)
