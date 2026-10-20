import uuid
from datetime import timedelta
from urllib.parse import urlsplit

from app.almacen.base import Almacen
from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.crypto.indice_ciego import sha256_hex
from app.exceptions.base import RecursoNoEncontradoError
from app.imagenes.base import DescargadorImagenes, ImagenCandidata, ImagenesClient, ImagenProcesada
from app.imagenes.licencias import LicenciaAbierta, licencia_permitida, normalizar_licencia
from app.models.enums import CategoriaImagen, EstadoTrabajoVisual, TipoRecursoVisual
from app.models.recurso_visual import RecursoVisual
from app.models.trabajo_visual import TrabajoVisual
from app.repositories.visual import RecursoVisualRepository, TrabajoVisualRepository
from app.schemas.archivo import ArchivoDescarga
from app.schemas.bloques import Diagrama
from app.schemas.visual import ImagenPublica, VisualPublico
from app.services.concurrencia import consultar_en_paralelo
from app.services.seguridad.moderacion_service import ModeracionService
from app.services.seguridad.textos import AVISO_ILUSTRACION_IA
from app.validators.texto import limpiar_texto_externo, normalizar_para_comparar

VERSION_ESTRATEGIA = "v1"
IDIOMA = "es"
ESQUEMA_SEGURO = "https"
MIMES_RASTER = {"image/jpeg", "image/png", "image/webp"}
MIME_SVG = "image/svg+xml"
EXTENSION_MINIATURA = ".png"
CANDIDATAS_POR_PROVEEDOR = 5
INTENTOS_DESCARGA = 3
MAX_TITULO = 300
MAX_DESCRIPCION = 300
MAX_AUTOR = 200
MAX_LICENCIA = 60
MAX_URL = 500
LONGITUD_MIN_TERMINO = 4
RUTA_IMAGEN = "/api/v1/recursos/{id_recurso}/imagen"
PREFIJO_CLAVE = "recursos"
CATEGORIAS_PREFERIDAS = {CategoriaImagen.CIENCIA_Y_GOBIERNO, CategoriaImagen.PATRIMONIO_ABIERTO}


def clave_cache(concepto: str, tipo: TipoRecursoVisual) -> str:
    return sha256_hex(
        f"{normalizar_para_comparar(concepto)}|{IDIOMA}|{tipo.value}|{VERSION_ESTRATEGIA}"
    )


class RecursoVisualService:
    """Imágenes reales con licencia abierta: búsqueda por concepto, filtrado de licencias,
    copia segura en el almacén propio y caché. También hidrata el recurso para la API."""

    def __init__(
        self,
        clientes: list[ImagenesClient],
        descargador: DescargadorImagenes,
        almacen: Almacen,
        moderacion: ModeracionService,
        recursos: RecursoVisualRepository,
        trabajos: TrabajoVisualRepository,
        settings: Settings,
    ) -> None:
        self._clientes = clientes
        self._descargador = descargador
        self._almacen = almacen
        self._moderacion = moderacion
        self._recursos = recursos
        self._trabajos = trabajos
        self._settings = settings

    def reutilizable(self, concepto: str, tipo: TipoRecursoVisual) -> RecursoVisual | None:
        recurso = self._recursos.obtener_por_clave_cache(clave_cache(concepto, tipo))
        if recurso is None or (recurso.fecha_expiracion and recurso.fecha_expiracion < ahora_utc()):
            return None
        return recurso

    def buscar_candidata(self, concepto: str) -> RecursoVisual | None:
        tareas = [
            (lambda c=cliente: c.buscar(concepto, CANDIDATAS_POR_PROVEEDOR))
            for cliente in self._clientes
        ]
        candidatas = consultar_en_paralelo(tareas, self._settings.imagenes_timeout_segundos)
        ordenadas = self._ordenar([c for c in candidatas if self._es_valida(c)], concepto)
        for candidata in ordenadas[:INTENTOS_DESCARGA]:
            imagen = self._copiar(candidata)
            if imagen is not None:
                return self._guardar_real(concepto, candidata, imagen)
        return None

    def crear_diagrama(self, concepto: str, diagrama: Diagrama) -> RecursoVisual:
        return self._recursos.agregar(
            RecursoVisual(
                tipo=TipoRecursoVisual.DIAGRAMA,
                clave_cache=clave_cache(concepto, TipoRecursoVisual.DIAGRAMA),
                concepto_canonico=concepto[:100],
                titulo=diagrama.titulo,
                datos_diagrama=diagrama.model_dump(mode="json"),
                fecha_creacion=ahora_utc(),
            )
        )

    def guardar_ilustracion(
        self, concepto: str, descripcion: str, imagen: ImagenProcesada, modelo: str
    ) -> RecursoVisual:
        clave = self._guardar_en_almacen(imagen)
        return self._recursos.agregar(
            RecursoVisual(
                tipo=TipoRecursoVisual.IA,
                clave_cache=clave_cache(concepto, TipoRecursoVisual.IA),
                concepto_canonico=concepto[:100],
                titulo=descripcion[:MAX_TITULO],
                descripcion=descripcion[:MAX_DESCRIPCION],
                ancho=imagen.ancho,
                alto=imagen.alto,
                clave_almacen=clave,
                modelo_ia=modelo[:60],
                fecha_creacion=ahora_utc(),
                fecha_expiracion=ahora_utc() + timedelta(days=self._settings.imagenes_cache_dias),
            )
        )

    def obtener_imagen(self, id_usuario: uuid.UUID, id_recurso: uuid.UUID) -> ArchivoDescarga:
        recurso = self._recursos.obtener_por_id(id_recurso)
        if recurso is None or recurso.clave_almacen is None:
            raise RecursoNoEncontradoError()
        # Solo quien recibió el recurso en una de sus respuestas puede descargarlo.
        if not self._trabajos.existe_para_usuario(id_recurso, id_usuario):
            raise RecursoNoEncontradoError()
        return ArchivoDescarga(
            f"{id_recurso}.webp", self._almacen.leer(recurso.clave_almacen), "image/webp"
        )

    def hidratar(self, trabajo: TrabajoVisual, recurso: RecursoVisual | None) -> VisualPublico:
        if trabajo.estado != EstadoTrabajoVisual.LISTO or recurso is None:
            return VisualPublico(
                estado=trabajo.estado,
                tipo=None,
                imagen=None,
                diagrama=None,
                generado_por_ia=False,
                aviso_ia=None,
            )
        es_ia = recurso.tipo == TipoRecursoVisual.IA
        return VisualPublico(
            estado=trabajo.estado,
            tipo=recurso.tipo,
            imagen=self._imagen_publica(recurso, trabajo.descripcion_visual),
            diagrama=Diagrama.model_validate(recurso.datos_diagrama)
            if recurso.datos_diagrama
            else None,
            generado_por_ia=es_ia,
            aviso_ia=AVISO_ILUSTRACION_IA if es_ia else None,
        )

    def obtener_recurso(self, id_recurso: uuid.UUID | None) -> RecursoVisual | None:
        return self._recursos.obtener_por_id(id_recurso) if id_recurso else None

    @staticmethod
    def _imagen_publica(recurso: RecursoVisual, texto_alternativo: str) -> ImagenPublica | None:
        if recurso.clave_almacen is None:
            return None
        return ImagenPublica(
            url=RUTA_IMAGEN.format(id_recurso=recurso.id_recurso),
            texto_alternativo=texto_alternativo,
            pie=recurso.titulo,
            autor=recurso.autor,
            licencia=recurso.licencia,
            url_licencia=recurso.url_licencia,
            url_origen=recurso.url_origen,
            proveedor=recurso.proveedor,
        )

    def _dominios_de(self, proveedor: str) -> list[str]:
        return next((c.dominios for c in self._clientes if c.proveedor == proveedor), [])

    def _es_valida(self, candidata: ImagenCandidata) -> bool:
        partes = urlsplit(candidata.url_archivo)
        dominios = self._dominios_de(candidata.proveedor)
        dominio_ok = any(
            partes.hostname == d or (partes.hostname or "").endswith(f".{d}") for d in dominios
        )
        miniatura_svg = candidata.mime == MIME_SVG and EXTENSION_MINIATURA in partes.path.lower()
        return (
            partes.scheme == ESQUEMA_SEGURO
            and dominio_ok
            and (candidata.mime in MIMES_RASTER or miniatura_svg)
            and candidata.ancho >= self._settings.imagenes_ancho_minimo
            and licencia_permitida(
                self._licencia(candidata), self._settings.imagenes_licencias_permitidas
            )
        )

    @staticmethod
    def _licencia(candidata: ImagenCandidata) -> LicenciaAbierta | None:
        return normalizar_licencia(candidata.licencia) or normalizar_licencia(
            candidata.url_licencia
        )

    def _ordenar(self, candidatas: list[ImagenCandidata], concepto: str) -> list[ImagenCandidata]:
        terminos = {
            t for t in normalizar_para_comparar(concepto).split() if len(t) >= LONGITUD_MIN_TERMINO
        }

        def puntaje(c: ImagenCandidata) -> tuple[int, int, int]:
            texto = normalizar_para_comparar(f"{c.titulo} {c.descripcion}")
            licencia = self._licencia(c)
            return (
                sum(1 for t in terminos if t in texto),
                int(licencia is not None and not licencia.requiere_atribucion),
                int(c.categoria in CATEGORIAS_PREFERIDAS),
            )

        return sorted(candidatas, key=puntaje, reverse=True)

    def _copiar(self, candidata: ImagenCandidata) -> ImagenProcesada | None:
        imagen = self._descargador.intentar_descargar(
            candidata.url_archivo, self._dominios_de(candidata.proveedor)
        )
        if imagen is None:
            return None
        if self._settings.imagenes_moderar_externas and not self._moderacion.imagen_es_apropiada(
            imagen.contenido, imagen.mime
        ):
            return None
        return imagen

    def _guardar_en_almacen(self, imagen: ImagenProcesada) -> str:
        clave = f"{PREFIJO_CLAVE}/{uuid.uuid4()}"
        self._almacen.guardar(clave, imagen.contenido, imagen.mime)
        return clave

    def _guardar_real(
        self, concepto: str, candidata: ImagenCandidata, imagen: ImagenProcesada
    ) -> RecursoVisual:
        licencia = self._licencia(candidata)
        assert licencia is not None
        return self._recursos.agregar(
            RecursoVisual(
                tipo=TipoRecursoVisual.REAL,
                clave_cache=clave_cache(concepto, TipoRecursoVisual.REAL),
                concepto_canonico=concepto[:100],
                titulo=limpiar_texto_externo(candidata.titulo, MAX_TITULO) or concepto,
                descripcion=limpiar_texto_externo(candidata.descripcion, MAX_DESCRIPCION) or None,
                proveedor=candidata.proveedor[:40],
                categoria=candidata.categoria,
                url_origen=candidata.url_origen[:MAX_URL],
                autor=limpiar_texto_externo(candidata.autor, MAX_AUTOR) or None,
                licencia=licencia.nombre[:MAX_LICENCIA],
                url_licencia=(candidata.url_licencia or licencia.url)[:MAX_URL],
                ancho=imagen.ancho,
                alto=imagen.alto,
                clave_almacen=self._guardar_en_almacen(imagen),
                fecha_creacion=ahora_utc(),
                fecha_expiracion=ahora_utc() + timedelta(days=self._settings.imagenes_cache_dias),
            )
        )
