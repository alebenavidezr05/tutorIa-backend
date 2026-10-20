import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import CategoriaImagen, TipoRecursoVisual
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class RecursoVisual(Base):
    __tablename__ = "recurso_visual"

    id_recurso: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    tipo: Mapped[TipoRecursoVisual] = mapped_column(tipo_enum(TipoRecursoVisual))
    clave_cache: Mapped[str] = mapped_column(String(64), unique=True)
    concepto_canonico: Mapped[str] = mapped_column(String(100))
    titulo: Mapped[str] = mapped_column(String(300))
    descripcion: Mapped[str | None] = mapped_column(String(300))
    proveedor: Mapped[str | None] = mapped_column(String(40))
    categoria: Mapped[CategoriaImagen | None] = mapped_column(tipo_enum(CategoriaImagen))
    url_origen: Mapped[str | None] = mapped_column(String(500))
    autor: Mapped[str | None] = mapped_column(String(200))
    licencia: Mapped[str | None] = mapped_column(String(60))
    url_licencia: Mapped[str | None] = mapped_column(String(300))
    ancho: Mapped[int | None] = mapped_column(Integer)
    alto: Mapped[int | None] = mapped_column(Integer)
    clave_almacen: Mapped[str | None] = mapped_column(String(200))
    modelo_ia: Mapped[str | None] = mapped_column(String(60))
    datos_diagrama: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    fecha_creacion: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_expiracion: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
