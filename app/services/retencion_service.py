from dataclasses import dataclass
from datetime import datetime, timedelta

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.models.autorizacion_acudiente import AutorizacionAcudiente
from app.models.enums import EstadoAutorizacion
from app.models.usuario import Usuario
from app.repositories.archivo import ArchivoRepository
from app.repositories.autorizacion import AutorizacionRepository
from app.repositories.conversacion import ConversacionRepository
from app.repositories.seguridad import AlertaSeguridadRepository
from app.repositories.uso import ConsumoIARepository
from app.repositories.usuario import UsuarioRepository
from app.repositories.verificacion_correo import VerificacionCorreoRepository
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
    cuentas_pendientes_eliminadas: int
    cuentas_no_verificadas_eliminadas: int


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
        usuarios: UsuarioRepository,
        verificaciones: VerificacionCorreoRepository,
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
        self._usuarios = usuarios
        self._verificaciones = verificaciones
        self._supresor = supresor
        self._almacen = almacen
        self._settings = settings
        self._uow = uow

    def limpiar(self) -> ResumenLimpieza:
        archivos, pendientes = self._limpiar_archivos()
        claves_no_verificadas = self._eliminar_cuentas_no_verificadas()
        claves_cuentas = self._eliminar_cuentas_pendientes()
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
            cuentas_pendientes_eliminadas=len(claves_cuentas),
            cuentas_no_verificadas_eliminadas=len(claves_no_verificadas),
        )
        self._uow.commit()
        self._almacen.eliminar_sin_fallar(
            c for claves in (*claves_cuentas, *claves_no_verificadas) for c in claves
        )
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

    def _eliminar_cuentas_pendientes(self) -> list[list[str]]:
        """Cuenta de menor que nadie autorizó (pendiente, rechazada, expirada o revocada) durante
        RETENCION_PENDIENTE_DIAS desde su último movimiento: se suprime con sus solicitudes y el
        correo del acudiente. Pendiente de revisión del abogado. Devuelve claves del almacén."""
        limite = self._hace(self._settings.retencion_pendiente_dias)
        eliminadas: list[list[str]] = []
        for usuario in self._usuarios.listar_pendientes_autorizacion():
            solicitudes = self._autorizaciones.listar_por_estudiante(usuario.correo_hash)
            if self._ultimo_movimiento(usuario, solicitudes) >= limite:
                continue
            eliminadas.append(self._eliminar_cuenta(usuario))
        return eliminadas

    def _eliminar_cuentas_no_verificadas(self) -> list[list[str]]:
        """Cuenta que no verificó su correo en RETENCION_NO_VERIFICADA_DIAS: se suprime con sus
        tokens (libera correos ocupados por registros ajenos). Pendiente de revisión legal."""
        limite = self._hace(self._settings.retencion_no_verificada_dias)
        return [
            self._eliminar_cuenta(usuario)
            for usuario in self._usuarios.listar_sin_verificar_desde_antes_de(limite)
        ]

    def _eliminar_cuenta(self, usuario: Usuario) -> list[str]:
        """Borra solicitudes al acudiente y tokens de verificación, y suprime la cuenta (antes de
        anonimizar, que cambia la huella del correo). Devuelve claves del almacén."""
        for solicitud in self._autorizaciones.listar_por_estudiante(usuario.correo_hash):
            self._autorizaciones.eliminar(solicitud)
        for verificacion in self._verificaciones.listar_por_usuario(usuario.id_usuario):
            self._verificaciones.eliminar(verificacion)
        return self._supresor.suprimir(usuario)

    @staticmethod
    def _ultimo_movimiento(usuario: Usuario, solicitudes: list[AutorizacionAcudiente]) -> datetime:
        fechas = [usuario.fecha_registro]
        for s in solicitudes:
            fechas.extend(
                f
                for f in (s.fecha_solicitud, s.fecha_verificacion, s.fecha_revocacion)
                if f is not None
            )
        return max(fechas)
