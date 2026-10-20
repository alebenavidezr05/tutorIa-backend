from dataclasses import dataclass
from datetime import datetime, timedelta

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.models.enums import EstadoAutorizacion
from app.repositories.archivo import ArchivoRepository
from app.repositories.autorizacion import AutorizacionRepository
from app.repositories.conversacion import ConversacionRepository
from app.repositories.seguridad import AlertaSeguridadRepository
from app.repositories.uso import ConsumoIARepository
from app.repositories.visual import RecursoVisualRepository
from app.services.supresor_datos import SupresorDatos


@dataclass(frozen=True)
class ResumenLimpieza:
    archivos: int
    archivos_pendientes: int
    conversaciones: int
    alertas: int
    consumos: int
    copias_imagenes: int
    autorizaciones_vencidas: int


class RetencionService:
    """Aplica los plazos de retención (`RETENCION_*`): lo vencido se borra; nada queda indefinido."""

    def __init__(
        self,
        archivos: ArchivoRepository,
        conversaciones: ConversacionRepository,
        alertas: AlertaSeguridadRepository,
        consumos: ConsumoIARepository,
        recursos: RecursoVisualRepository,
        autorizaciones: AutorizacionRepository,
        supresor: SupresorDatos,
        almacen: Almacen,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._archivos = archivos
        self._conversaciones = conversaciones
        self._alertas = alertas
        self._consumos = consumos
        self._recursos = recursos
        self._autorizaciones = autorizaciones
        self._supresor = supresor
        self._almacen = almacen
        self._settings = settings
        self._uow = uow

    def limpiar(self) -> ResumenLimpieza:
        archivos, pendientes = self._limpiar_archivos()
        resumen = ResumenLimpieza(
            archivos=archivos,
            archivos_pendientes=pendientes,
            conversaciones=self._borrar_conversaciones(),
            alertas=self._borrar_alertas(),
            consumos=self._consumos.eliminar_anteriores_a(
                self._hace(self._settings.retencion_consumo_dias)
            ),
            copias_imagenes=self._borrar_copias_imagenes(),
            autorizaciones_vencidas=self._vencer_autorizaciones(),
        )
        self._uow.commit()
        return resumen

    @staticmethod
    def _hace(dias: int) -> datetime:
        return ahora_utc() - timedelta(days=dias)

    def _limpiar_archivos(self) -> tuple[int, int]:
        vencidos = self._archivos.listar_vencidos(ahora_utc())
        fallidas = self._almacen.eliminar_sin_fallar(a.clave_almacen for a in vencidos)
        borrables = [a for a in vencidos if a.clave_almacen not in fallidas]
        for archivo in borrables:
            self._archivos.eliminar(archivo)
        return len(borrables), len(fallidas)

    def _borrar_conversaciones(self) -> int:
        viejas = self._conversaciones.listar_anteriores_a(
            self._hace(self._settings.retencion_mensajes_dias)
        )
        for conversacion in viejas:
            # Sus archivos quedan marcados para que la próxima limpieza borre también el almacén.
            self._supresor.marcar_archivos_eliminados(
                self._archivos.listar_por_contexto(conversacion.id_conversacion)
            )
            self._conversaciones.eliminar(conversacion)
        return len(viejas)

    def _borrar_alertas(self) -> int:
        viejas = self._alertas.listar_anteriores_a(
            self._hace(self._settings.retencion_alertas_dias)
        )
        for alerta in viejas:
            self._alertas.eliminar(alerta)
        return len(viejas)

    def _borrar_copias_imagenes(self) -> int:
        """La fila se conserva como referencia (APA); solo se borra la copia del archivo."""
        vencidos = [r for r in self._recursos.listar_vencidos(ahora_utc()) if r.clave_almacen]
        fallidas = self._almacen.eliminar_sin_fallar(
            r.clave_almacen for r in vencidos if r.clave_almacen
        )
        borrados = [r for r in vencidos if r.clave_almacen not in fallidas]
        for recurso in borrados:
            recurso.clave_almacen = None
        return len(borrados)

    def _vencer_autorizaciones(self) -> int:
        vencidas = self._autorizaciones.listar_pendientes_vencidas(ahora_utc())
        for autorizacion in vencidas:
            autorizacion.estado = EstadoAutorizacion.VENCIDA
        return len(vencidas)
