import csv
import io
import uuid

from app.models.enums import Capacidad
from app.models.plan_estudio import PlanEstudio
from app.repositories.plan import PlanEstudioRepository
from app.schemas.archivo import ArchivoDescarga
from app.services.suscripcion_service import SuscripcionService

NOMBRE_ARCHIVO = "progreso_tutoria.csv"
MIME_CSV = "text/csv; charset=utf-8"
# Excel interpreta como fórmula una celda que empieza por estos caracteres (inyección CSV).
INICIOS_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r")
ENCABEZADOS = (
    "tema",
    "nivel",
    "fecha_plan",
    "plan",
    "actividad",
    "estado_actividad",
    "fecha_completado",
)


def neutralizar_celda(valor: object) -> str:
    texto = "" if valor is None else str(valor)
    return f"'{texto}" if texto.startswith(INICIOS_PELIGROSOS) else texto


def _filas(plan: PlanEstudio) -> list[list[str]]:
    base = [
        plan.sesion.tema,
        plan.nivel_bloom.value,
        plan.fecha_generacion.date().isoformat(),
        plan.titulo,
    ]
    return [
        [neutralizar_celda(v) for v in (*base, a.enunciado, a.estado.value, a.fecha_completado)]
        for a in plan.actividades
    ]


class ReporteProgresoService:
    def __init__(self, planes: PlanEstudioRepository, suscripciones: SuscripcionService) -> None:
        self._planes = planes
        self._suscripciones = suscripciones

    def generar_csv(self, id_usuario: uuid.UUID) -> ArchivoDescarga:
        self._suscripciones.asegurar_capacidad(id_usuario, Capacidad.REPORTE_PROGRESO)
        salida = io.StringIO()
        escritor = csv.writer(salida)
        escritor.writerow(ENCABEZADOS)
        for plan in self._planes.listar_por_usuario(id_usuario):
            escritor.writerows(_filas(plan))
        # BOM para que Excel reconozca UTF-8 (tildes y eñes).
        return ArchivoDescarga(NOMBRE_ARCHIVO, salida.getvalue().encode("utf-8-sig"), MIME_CSV)
