import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.crypto.tipos import FechaCifrada, TextoCifrado
from app.models.enums import EstadoCuenta, TipoNivel
from app.models.tipos import FechaHoraUTC, nuevo_uuid, tipo_enum


class Usuario(Base):
    __tablename__ = "usuario"

    id_usuario: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=nuevo_uuid)
    nombre: Mapped[str] = mapped_column(TextoCifrado("usuario.nombre"))
    correo: Mapped[str] = mapped_column(TextoCifrado("usuario.correo"))
    correo_hash: Mapped[str] = mapped_column(String(64), unique=True)
    fecha_nacimiento: Mapped[date] = mapped_column(FechaCifrada("usuario.fecha_nacimiento"))
    hash_contrasena: Mapped[str] = mapped_column(String(60))
    nivel_educativo: Mapped[str] = mapped_column(String(30))
    tipo_nivel: Mapped[TipoNivel] = mapped_column(tipo_enum(TipoNivel))
    estado_cuenta: Mapped[EstadoCuenta] = mapped_column(
        tipo_enum(EstadoCuenta), default=EstadoCuenta.ACTIVA
    )
    fecha_aceptacion_tratamiento: Mapped[datetime] = mapped_column(FechaHoraUTC)
    version_texto_tratamiento: Mapped[str] = mapped_column(String(20))
    version_token: Mapped[int] = mapped_column(Integer, default=0)
    fecha_registro: Mapped[datetime] = mapped_column(FechaHoraUTC)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Cuentas anteriores a la verificación quedan en true (migración en core/migraciones.py).
    correo_verificado: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha_verificacion_correo: Mapped[datetime | None] = mapped_column(FechaHoraUTC)
