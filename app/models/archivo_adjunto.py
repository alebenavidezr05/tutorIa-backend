import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto.tipos import TextoCifrado
from app.models.enums import EstadoArchivo
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class ArchivoAdjunto(Base):
    __tablename__ = "archivo_adjunto"

    id_archivo: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuario.id_usuario"), index=True)
    id_actividad: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("actividad.id_actividad", ondelete="CASCADE")
    )
    id_mensaje: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mensaje.id_mensaje", ondelete="CASCADE")
    )
    # Contexto de subida (conversación o actividad) para validar que se adjunte al mismo lugar.
    id_contexto: Mapped[uuid.UUID] = mapped_column(Uuid)
    nombre_original: Mapped[str] = mapped_column(TextoCifrado("archivo_adjunto.nombre_original"))
    mime: Mapped[str] = mapped_column(String(50))
    tamano_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    clave_almacen: Mapped[str] = mapped_column(String(200))
    estado: Mapped[EstadoArchivo] = mapped_column(tipo_enum(EstadoArchivo))
    fecha_creacion: Mapped[datetime] = mapped_column(FechaHoraUTC)
    fecha_expiracion: Mapped[datetime] = mapped_column(FechaHoraUTC)
