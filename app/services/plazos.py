from datetime import date

from app.core.config import Settings
from app.models.enums import TipoSolicitud
from app.validators.fechas import sumar_dias_habiles

TIPOS_CONSULTA = {TipoSolicitud.CONSULTA}


def fecha_limite_solicitud(tipo: TipoSolicitud, recibida: date, settings: Settings) -> date:
    """Consultas: 10 días hábiles; reclamos, rectificación, supresión y revocatoria: 15 (Ley 1581)."""
    dias = (
        settings.privacidad_plazo_consulta_dias_habiles
        if tipo in TIPOS_CONSULTA
        else settings.privacidad_plazo_reclamo_dias_habiles
    )
    return sumar_dias_habiles(recibida, dias, set(settings.festivos_co))
