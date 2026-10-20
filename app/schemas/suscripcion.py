from datetime import datetime

from pydantic import BaseModel

from app.models.enums import EstadoSuscripcion, PlanSuscripcion


class LimitesPublicos(BaseModel):
    mensajes_restantes_hoy: int
    planes_restantes_hoy: int
    imagenes_ia_restantes_hoy: int
    busquedas_video_restantes_hoy: int
    archivos_restantes_hoy: int


class SuscripcionPublica(BaseModel):
    plan: PlanSuscripcion
    estado: EstadoSuscripcion
    fecha_inicio: datetime
    fecha_fin: datetime | None
    capacidades: list[str]
    limites: LimitesPublicos


class CheckoutPublico(BaseModel):
    url_pago: str
