import uuid

from app.core.config import Settings
from app.models.enums import Capacidad
from app.repositories.plan import PlanEstudioRepository
from app.schemas.historial import HistorialPagina, ItemHistorial
from app.services.suscripcion_service import SuscripcionService
from app.validators.propiedad import validar_propietario


class HistorialService:
    def __init__(
        self, planes: PlanEstudioRepository, suscripciones: SuscripcionService, settings: Settings
    ) -> None:
        self._planes = planes
        self._suscripciones = suscripciones
        self._settings = settings

    def listar(
        self, uid: uuid.UUID, id_usuario_actual: uuid.UUID, pagina: int, tamano: int
    ) -> HistorialPagina:
        validar_propietario(uid, id_usuario_actual)
        limitado = not self._suscripciones.tiene_capacidad(uid, Capacidad.HISTORIAL_COMPLETO)
        total = self._planes.contar_por_usuario(uid)
        visibles = min(total, self._settings.historial_items_gratis) if limitado else total
        desplazamiento = (pagina - 1) * tamano
        limite = max(min(tamano, visibles - desplazamiento), 0)
        planes = self._planes.listar_historial(uid, desplazamiento, limite) if limite else []
        items = [
            ItemHistorial(
                id_sesion=p.id_sesion,
                id_plan=p.id_plan,
                tema=p.sesion.tema,
                nivel_estimado=p.sesion.nivel_estimado,
                fecha=p.fecha_generacion,
            )
            for p in planes
        ]
        return HistorialPagina(
            items=items, total=visibles, pagina=pagina, tamano=tamano, limitado=limitado
        )
