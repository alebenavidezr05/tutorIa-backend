import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    EstadoSolicitud,
    FinalidadConsentimiento,
    OtorgadoPor,
    TipoSolicitud,
)

MAX_DETALLE_SOLICITUD = 2000


class ResponsablePublico(BaseModel):
    razon_social: str
    nit: str
    domicilio: str
    correo_datos: str


class FinalidadPublica(BaseModel):
    finalidad: FinalidadConsentimiento
    obligatoria: bool
    texto: str


class PoliticaPublica(BaseModel):
    version: str
    texto: str
    responsable: ResponsablePublico
    finalidades: list[FinalidadPublica]
    vigente_desde: str


class ConsentimientoPublico(BaseModel):
    finalidad: FinalidadConsentimiento
    otorgado: bool
    otorgado_por: OtorgadoPor
    version_politica: str
    fecha: datetime


class CambioConsentimientoEntrada(BaseModel):
    finalidad: FinalidadConsentimiento
    otorgado: bool
    version_politica: str = Field(min_length=1, max_length=20)


class AceptarPoliticaEntrada(BaseModel):
    version_politica: str = Field(min_length=1, max_length=20)
    acepta_tratamiento: bool = False
    acepta_transferencia_internacional: bool = False


class SolicitudEntrada(BaseModel):
    tipo: TipoSolicitud
    detalle: str = Field(min_length=5, max_length=MAX_DETALLE_SOLICITUD)


class SolicitudPublica(BaseModel):
    id_solicitud: uuid.UUID
    tipo: TipoSolicitud
    estado: EstadoSolicitud
    fecha_limite: date


class MisDatos(BaseModel):
    usuario: dict[str, Any]
    perfil_aprendizaje: dict[str, Any]
    planes: list[dict[str, Any]]
    conversaciones: list[dict[str, Any]]
    archivos: list[dict[str, Any]]
    consentimientos: list[ConsentimientoPublico]
    solicitudes: list[SolicitudPublica]


class ProveedorDatos(BaseModel):
    nombre: str
    datos_enviados: str
    finalidad: str


class CumplimientoPublico(BaseModel):
    proveedores: list[ProveedorDatos]
    edad_minima: int
    retencion_dias: dict[str, int]
    contacto: str
