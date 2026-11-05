from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.tipos import FechaHoraUTC


class CacheFuentes(Base):
    """Resultado normalizado de una búsqueda por proveedor, idioma y tema normalizado. La clave es
    un SHA-256: el texto del tema (dato del estudiante) no se guarda en claro."""

    __tablename__ = "cache_fuentes"

    clave_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    proveedor: Mapped[str] = mapped_column(String(40), index=True)
    candidatas: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    fecha_creacion: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_expiracion: Mapped[datetime] = mapped_column(FechaHoraUTC, index=True)
