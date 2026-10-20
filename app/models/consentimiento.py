import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import FinalidadConsentimiento, OtorgadoPor
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class Consentimiento(Base):
    """Solo inserciones: revocar es agregar una fila con `otorgado=False` (prueba conservada)."""

    __tablename__ = "consentimiento"

    id_consentimiento: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    id_usuario: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("usuario.id_usuario", ondelete="SET NULL")
    )
    id_autorizacion: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("autorizacion_acudiente.id_autorizacion", ondelete="SET NULL")
    )
    correo_hash: Mapped[str] = mapped_column(String(64), index=True)
    finalidad: Mapped[FinalidadConsentimiento] = mapped_column(tipo_enum(FinalidadConsentimiento))
    otorgado: Mapped[bool] = mapped_column(Boolean)
    otorgado_por: Mapped[OtorgadoPor] = mapped_column(tipo_enum(OtorgadoPor))
    version_politica: Mapped[str] = mapped_column(String(20))
    texto_sha256: Mapped[str] = mapped_column(String(64))
    medio: Mapped[str] = mapped_column(String(20), default="WEB")
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    fecha: Mapped[datetime] = mapped_column(FechaHoraUTC)
