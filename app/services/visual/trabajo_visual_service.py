import logging
import time
import uuid
from datetime import timedelta

from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.core.unit_of_work import UnitOfWork
from app.crypto.indice_ciego import IndiceCiego
from app.exceptions.base import (
    AppError,
    ContenidoNoPermitidoError,
    RecursoNoEncontradoError,
)
from app.imagenes.base import ImagenesIAClient, ImagenProcesada, ProcesadorImagenes
from app.imagenes.constantes import construir_prompt_imagen
from app.models.enums import CampoUso, EstadoTrabajoVisual, TipoRecursoVisual, TipoVisualPreferido
from app.models.recurso_visual import RecursoVisual
from app.models.trabajo_visual import TrabajoVisual
from app.repositories.conversacion import MensajeRepository
from app.repositories.usuario import UsuarioRepository
from app.repositories.visual import TrabajoVisualRepository
from app.schemas.bloques import Diagrama, SolicitudVisual
from app.schemas.visual import VisualPublico
from app.services.consumo_service import ConsumoService, UsoTokens
from app.services.estudiante import perfil_estudiante
from app.services.seguridad.moderacion_service import ModeracionService
from app.services.uso_service import UsoService
from app.services.visual.recurso_visual_service import RecursoVisualService
from app.validators.diagrama import validar_diagrama
from app.validators.propiedad import validar_recurso_propio

logger = logging.getLogger(__name__)

ESTADOS_EN_CURSO = {EstadoTrabajoVisual.PENDIENTE, EstadoTrabajoVisual.PROCESANDO}
CODIGO_SIN_RECURSO = "SIN_RECURSO"
CODIGO_TIEMPO_AGOTADO = "TIEMPO_AGOTADO"
CODIGO_INTERNO = "ERROR_INTERNO"
PREFIJO_SAFETY = "openai-safety:"


class TiempoAgotadoError(AppError):
    codigo = CODIGO_TIEMPO_AGOTADO


class SinRecursoError(AppError):
    codigo = CODIGO_SIN_RECURSO


def codigo_error(exc: Exception) -> str:
    """Código normalizado: nunca se guarda la traza ni datos del estudiante."""
    return exc.codigo if isinstance(exc, AppError) else CODIGO_INTERNO


class TrabajoVisualService:
    """Resuelve el recurso visual en segundo plano. Orden: reutilizar → imagen real abierta →
    diagrama propio → ilustración IA (solo como último recurso y sin exigencia de exactitud)."""

    def __init__(
        self,
        trabajos: TrabajoVisualRepository,
        mensajes: MensajeRepository,
        usuarios: UsuarioRepository,
        recursos: RecursoVisualService,
        imagenes_ia: ImagenesIAClient,
        procesador: ProcesadorImagenes,
        moderacion: ModeracionService,
        uso: UsoService,
        consumo: ConsumoService,
        indice: IndiceCiego,
        settings: Settings,
        uow: UnitOfWork,
    ) -> None:
        self._trabajos = trabajos
        self._mensajes = mensajes
        self._usuarios = usuarios
        self._recursos = recursos
        self._imagenes_ia = imagenes_ia
        self._procesador = procesador
        self._moderacion = moderacion
        self._uso = uso
        self._consumo = consumo
        self._indice = indice
        self._settings = settings
        self._uow = uow

    def crear(
        self, id_mensaje: uuid.UUID, id_usuario: uuid.UUID, solicitud: SolicitudVisual
    ) -> TrabajoVisual:
        """No confirma: se crea dentro de la transacción del turno del tutor."""
        return self._trabajos.agregar(
            TrabajoVisual(
                id_mensaje=id_mensaje,
                id_usuario=id_usuario,
                estado=EstadoTrabajoVisual.PENDIENTE,
                concepto_canonico=solicitud.concepto_canonico,
                tipo_preferido=solicitud.tipo_preferido,
                descripcion_visual=solicitud.descripcion_visual,
                exige_exactitud=solicitud.exige_exactitud,
                datos_diagrama=solicitud.diagrama.model_dump(mode="json")
                if solicitud.diagrama
                else None,
                intentos=0,
                fecha_creacion=ahora_utc(),
            )
        )

    def procesar(self, id_trabajo: uuid.UUID) -> None:
        trabajo = self._trabajos.obtener_por_id(id_trabajo)
        if trabajo is None or trabajo.estado != EstadoTrabajoVisual.PENDIENTE:
            return
        self._marcar_procesando(trabajo)
        try:
            recurso = self._resolver(
                trabajo, time.monotonic() + self._settings.trabajo_visual_timeout_segundos
            )
        except (
            Exception
        ) as exc:  # El fallo se persiste como estado FALLIDO, sin reintentos que paguen dos veces.
            self._uow.rollback()
            self._marcar_fallido(id_trabajo, codigo_error(exc))
            logger.warning("trabajo_visual_fallido codigo=%s", codigo_error(exc))
            return
        trabajo.id_recurso = recurso.id_recurso
        trabajo.estado = EstadoTrabajoVisual.LISTO
        trabajo.fecha_fin = ahora_utc()
        self._uow.commit()

    def consultar(self, id_usuario: uuid.UUID, id_mensaje: uuid.UUID) -> VisualPublico:
        mensaje = self._mensajes.obtener_con_conversacion(id_mensaje)
        if mensaje is None:
            raise RecursoNoEncontradoError()
        validar_recurso_propio(mensaje.conversacion.id_usuario, id_usuario)
        trabajo = self._trabajos.obtener_por_mensaje(id_mensaje)
        if trabajo is None:
            raise RecursoNoEncontradoError()
        if self._esta_vencido(trabajo):
            self._fallar(trabajo, CODIGO_TIEMPO_AGOTADO)
            self._uow.commit()
        return self.vista(trabajo)

    def vista(self, trabajo: TrabajoVisual) -> VisualPublico:
        return self._recursos.hidratar(trabajo, self._recursos.obtener_recurso(trabajo.id_recurso))

    def vista_opcional(self, trabajo: TrabajoVisual | None) -> VisualPublico | None:
        return self.vista(trabajo) if trabajo is not None else None

    def recuperar_huerfanos(self) -> int:
        limite = ahora_utc() - timedelta(seconds=self._settings.trabajo_visual_timeout_segundos)
        huerfanos = self._trabajos.listar_procesando_antes_de(limite)
        for trabajo in huerfanos:
            self._fallar(trabajo, CODIGO_TIEMPO_AGOTADO)
        self._uow.commit()
        return len(huerfanos)

    def _marcar_procesando(self, trabajo: TrabajoVisual) -> None:
        trabajo.estado = EstadoTrabajoVisual.PROCESANDO
        trabajo.fecha_inicio = ahora_utc()
        trabajo.intentos += 1
        self._uow.commit()

    def _marcar_fallido(self, id_trabajo: uuid.UUID, codigo: str) -> None:
        trabajo = self._trabajos.obtener_por_id(id_trabajo)
        if trabajo is not None:
            self._fallar(trabajo, codigo)
            self._uow.commit()

    @staticmethod
    def _fallar(trabajo: TrabajoVisual, codigo: str) -> None:
        trabajo.estado = EstadoTrabajoVisual.FALLIDO
        trabajo.codigo_error = codigo[:50]
        trabajo.fecha_fin = ahora_utc()

    def _esta_vencido(self, trabajo: TrabajoVisual) -> bool:
        limite = trabajo.fecha_creacion + timedelta(
            seconds=self._settings.trabajo_visual_timeout_segundos
        )
        return trabajo.estado in ESTADOS_EN_CURSO and limite < ahora_utc()

    def _resolver(self, trabajo: TrabajoVisual, limite: float) -> RecursoVisual:
        diagrama = self._diagrama_valido(trabajo)
        reutilizado = self._reutilizable(trabajo, diagrama)
        if reutilizado is not None:
            return reutilizado
        if self._admite_imagen_real(trabajo, diagrama):
            real = self._recursos.buscar_candidata(trabajo.concepto_canonico)
            if real is not None:
                return real
        if diagrama is not None:
            return self._recursos.crear_diagrama(trabajo.concepto_canonico, diagrama)
        self._verificar_tiempo(limite)
        return self._ilustrar(trabajo)

    @staticmethod
    def _diagrama_valido(trabajo: TrabajoVisual) -> Diagrama | None:
        if not trabajo.datos_diagrama:
            return None
        diagrama = Diagrama.model_validate(trabajo.datos_diagrama)
        return None if validar_diagrama(diagrama) else diagrama

    def _reutilizable(
        self, trabajo: TrabajoVisual, diagrama: Diagrama | None
    ) -> RecursoVisual | None:
        tipos = [TipoRecursoVisual.REAL] if self._admite_imagen_real(trabajo, diagrama) else []
        tipos += [TipoRecursoVisual.DIAGRAMA] if diagrama is not None else []
        tipos += [TipoRecursoVisual.IA] if self._admite_ilustracion(trabajo) else []
        return next(
            (r for t in tipos if (r := self._recursos.reutilizable(trabajo.concepto_canonico, t))),
            None,
        )

    @staticmethod
    def _admite_imagen_real(trabajo: TrabajoVisual, diagrama: Diagrama | None) -> bool:
        prefiere_diagrama = (
            trabajo.tipo_preferido == TipoVisualPreferido.DIAGRAMA and diagrama is not None
        )
        return not trabajo.exige_exactitud and not prefiere_diagrama

    def _admite_ilustracion(self, trabajo: TrabajoVisual) -> bool:
        # La exactitud (matemáticas, anatomía, etiquetas) nunca se confía a una imagen generada.
        return self._settings.imagenes_ia_activa and not trabajo.exige_exactitud

    @staticmethod
    def _verificar_tiempo(limite: float) -> None:
        if time.monotonic() > limite:
            raise TiempoAgotadoError()

    def _ilustrar(self, trabajo: TrabajoVisual) -> RecursoVisual:
        if not self._admite_ilustracion(trabajo):
            raise SinRecursoError()
        self._uso.asegurar_disponible(trabajo.id_usuario, CampoUso.IMAGENES_IA)
        self._consumo.asegurar_presupuesto_imagenes()
        if not self._moderacion.texto_es_apropiado(trabajo.descripcion_visual):
            raise ContenidoNoPermitidoError()
        imagen = self._generar(trabajo)
        self._uso.consumir(trabajo.id_usuario, CampoUso.IMAGENES_IA)
        if not self._moderacion.imagen_es_apropiada(imagen.contenido, imagen.mime):
            raise ContenidoNoPermitidoError()
        return self._recursos.guardar_ilustracion(
            trabajo.concepto_canonico,
            trabajo.descripcion_visual,
            imagen,
            self._settings.imagenes_ia_modelo,
        )

    def _generar(self, trabajo: TrabajoVisual) -> ImagenProcesada:
        usuario = self._usuarios.obtener_por_id(trabajo.id_usuario)
        if usuario is None:
            raise RecursoNoEncontradoError()
        grupo = perfil_estudiante(usuario, self._settings).grupo_edad
        prompt = construir_prompt_imagen(trabajo.descripcion_visual, grupo.value)
        safety = self._indice.calcular(f"{PREFIJO_SAFETY}{trabajo.id_usuario}")
        generada = self._imagenes_ia.generar(prompt, safety)
        uso = UsoTokens(generada.tokens_entrada or 0, generada.tokens_salida or 0)
        self._consumo.registrar_imagen(trabajo.id_usuario, generada.modelo, uso, exito=True)
        return self._procesador.recodificar(generada.contenido, self._settings.imagenes_lado_maximo)
