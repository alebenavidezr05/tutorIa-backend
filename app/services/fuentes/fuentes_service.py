import json
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlsplit

from app.core.config import Settings
from app.core.tiempo import ahora_utc
from app.crypto.indice_ciego import sha256_hex
from app.exceptions.base import TemaSinFuentesError
from app.fuentes.base import AUTORIDAD_PISO, FuenteCandidata, FuentesClient
from app.fuentes.bloqueo import es_dominio_bloqueado, sin_bloqueadas
from app.llm.prompts import FuenteContexto
from app.models.enums import CategoriaFuente, NivelCognitivo, TipoFuente, TipoNivel
from app.models.fuente import Fuente
from app.repositories.fuente import FuenteRepository
from app.schemas.fuente import FuentePublica
from app.services.concurrencia import consultar_en_paralelo
from app.services.presentacion import fuente_publica
from app.validators.fuentes import cumple_autoridad_minima
from app.validators.texto import limpiar_texto_externo, normalizar_para_comparar

logger = logging.getLogger(__name__)

LONGITUD_MIN_TERMINO = 4
MAX_TITULO = 300
MAX_AUTOR = 200
MAX_SITIO = 100
MAX_URL = 500
MAX_DOI = 100
MAX_LICENCIA = 60
LONGITUD_IDIOMA = 2
ESQUEMA_SEGURO = "https"
CATEGORIAS_EXIGIDAS_AVANZADO = {
    CategoriaFuente.ACADEMICA_ABIERTA,
    CategoriaFuente.INSTITUCIONAL_OFICIAL,
}
CATEGORIAS_ESCOLARES = {
    CategoriaFuente.EDUCATIVA_ABIERTA,
    CategoriaFuente.REFERENCIA,
    CategoriaFuente.INSTITUCIONAL_OFICIAL,
}


@dataclass(frozen=True)
class ContextoFuentes:
    nivel: NivelCognitivo
    tipo_nivel: TipoNivel


class FuentesService:
    """Recupera fuentes verificables por categoría, sin LLM y de forma determinista (§12.2).
    Las fuentes nuevas quedan pendientes en memoria y se guardan con el commit del caso de uso,
    para no abrir escrituras antes de llamar al modelo."""

    def __init__(
        self, clientes: list[FuentesClient], fuentes: FuenteRepository, settings: Settings
    ) -> None:
        self._clientes = clientes
        self._fuentes = fuentes
        self._settings = settings
        self._pendientes: dict[uuid.UUID, Fuente] = {}
        self._refrescos: dict[uuid.UUID, tuple[Fuente, FuenteCandidata]] = {}

    def recopilar(self, consulta: str, contexto: ContextoFuentes) -> list[Fuente]:
        categorias = self._categorias(contexto)
        candidatas = self._aceptables(self._consultar(consulta, categorias))
        minimo = self.autoridad_minima(contexto.nivel)
        if not cumple_autoridad_minima(self._autoridades_que_respaldan(candidatas), minimo):
            # Respaldo: si las categorías escolares no alcanzan la autoridad mínima, se suman las
            # académicas abiertas para no dejar sin fuentes verificables al estudiante.
            respaldo = self._consultar(consulta, {CategoriaFuente.ACADEMICA_ABIERTA} - categorias)
            candidatas += self._aceptables(respaldo)
        unicas = self._deduplicar(candidatas)
        elegidas = self._seleccionar(self._ordenar(unicas, consulta), contexto)
        return [*self._curadas(consulta), *self._materializar(elegidas)][
            : self._settings.fuentes_max_por_turno
        ]

    def recopilar_suficientes(self, consulta: str, contexto: ContextoFuentes) -> list[Fuente]:
        fuentes = self.recopilar(consulta, contexto)
        minimo = self.autoridad_minima(contexto.nivel)
        if self._settings.fuentes_obligatorias and not cumple_autoridad_minima(
            self._autoridades_que_respaldan(fuentes), minimo
        ):
            raise TemaSinFuentesError()
        return fuentes

    def buscar_para_herramienta(
        self, consulta: str, contexto: ContextoFuentes
    ) -> tuple[str, list[Fuente]]:
        fuentes = self.recopilar(consulta, contexto)
        resultado = [
            {
                "id_fuente": str(f.id_fuente),
                "titulo": f.titulo,
                "sitio": f.sitio,
                "categoria": f.categoria.value,
                "autoridad": f.autoridad,
                "extracto": (f.extracto or "")[: self._settings.fuentes_extracto_herramienta],
                "licencia": f.licencia,
            }
            for f in fuentes
        ]
        texto = json.dumps(resultado, ensure_ascii=False) if resultado else "Sin resultados."
        return texto, fuentes

    def persistir_pendientes(self) -> None:
        self._fuentes.agregar_varios(self._pendientes.values())
        for fuente, candidata in self._refrescos.values():
            self._refrescar(fuente, candidata)
        self._pendientes.clear()
        self._refrescos.clear()

    def vincular_a_mensaje(self, id_mensaje: uuid.UUID, ids_fuentes: Iterable[uuid.UUID]) -> None:
        self.persistir_pendientes()
        self._fuentes.vincular_mensaje(id_mensaje, set(ids_fuentes))

    def vincular_a_plan(self, id_plan: uuid.UUID, ids_fuentes: Iterable[uuid.UUID]) -> None:
        self.persistir_pendientes()
        self._fuentes.vincular_plan(id_plan, set(ids_fuentes))

    def autoridad_minima(self, nivel: NivelCognitivo) -> int:
        minimo: int = getattr(self._settings, f"autoridad_minima_{nivel.value.lower()}")
        return minimo

    def permitidas(self, fuentes: Iterable[Fuente]) -> list[Fuente]:
        """Filtro de lectura: una fila guardada antes de la lista de bloqueo (o bajo el piso de
        autoridad) nunca llega al modelo, a las citas ni a las referencias."""
        return [
            f
            for f in sin_bloqueadas(fuentes, self._settings.fuentes_dominios_bloqueados)
            if f.autoridad >= AUTORIDAD_PISO
        ]

    def autoridades(self, fuentes: Iterable[Fuente]) -> dict[uuid.UUID, int]:
        """Solo las fuentes permitidas: citar una bloqueada equivale a citar una inventada."""
        return {f.id_fuente: f.autoridad for f in self.permitidas(fuentes)}

    def a_contexto(self, fuentes: Iterable[Fuente]) -> list[FuenteContexto]:
        return [
            FuenteContexto(
                f.id_fuente, f.titulo, f.sitio, f.categoria.value, f.autoridad, f.extracto or ""
            )
            for f in self.permitidas(fuentes)
        ]

    @staticmethod
    def publicas(fuentes: Iterable[Fuente]) -> list[FuentePublica]:
        return [fuente_publica(f) for f in fuentes]

    def _categorias(self, contexto: ContextoFuentes) -> set[CategoriaFuente]:
        if (
            contexto.tipo_nivel == TipoNivel.UNIVERSIDAD_TECNICA
            or contexto.nivel == NivelCognitivo.AVANZADO
        ):
            return set(CategoriaFuente) - {CategoriaFuente.CURADA}
        return CATEGORIAS_ESCOLARES

    def _consultar(self, consulta: str, categorias: set[CategoriaFuente]) -> list[FuenteCandidata]:
        limite = self._settings.fuentes_max_por_turno
        idioma = self._settings.fuentes_idiomas[0]
        tareas = [
            (lambda c=cliente: c.buscar(consulta, idioma, limite))
            for cliente in self._clientes
            if cliente.categoria in categorias
        ]
        return consultar_en_paralelo(tareas, self._settings.fuentes_timeout_segundos)

    def _autoridades_que_respaldan(self, fuentes: Iterable[FuenteCandidata | Fuente]) -> list[int]:
        """La prensa aporta contexto, pero no cumple sola la autoridad mínima del nivel salvo que
        PRENSA_RESPALDA_SOLA lo permita (temas de actualidad)."""
        return [
            f.autoridad
            for f in fuentes
            if f.categoria != CategoriaFuente.PRENSA_CONFIABLE
            or self._settings.prensa_respalda_sola
        ]

    def _aceptables(self, candidatas: list[FuenteCandidata]) -> list[FuenteCandidata]:
        """Primero el bloqueo y el piso de autoridad, antes de deduplicar, ordenar o guardar."""
        aceptables = []
        for c in candidatas:
            if es_dominio_bloqueado(c.url, self._settings.fuentes_dominios_bloqueados):
                # Defecto del adaptador: se avisa sin URL ni datos del estudiante.
                logger.warning("fuente_bloqueada_descartada proveedor=%s", c.proveedor)
            elif c.autoridad >= AUTORIDAD_PISO and self._es_aceptable(c):
                aceptables.append(c)
        return aceptables

    def _es_aceptable(self, candidata: FuenteCandidata) -> bool:
        partes = urlsplit(candidata.url)
        dominios = self._settings.fuentes_dominios_permitidos
        dominio_ok = not dominios or any(partes.netloc.endswith(d) for d in dominios)
        idioma_ok = (
            not candidata.idioma
            or candidata.idioma[:LONGITUD_IDIOMA] in self._settings.fuentes_idiomas
        )
        identificable = bool(candidata.autor or candidata.sitio)
        return (
            partes.scheme == ESQUEMA_SEGURO
            and len(candidata.url) <= MAX_URL
            and dominio_ok
            and idioma_ok
            and identificable
            and bool(candidata.extracto.strip())
        )

    @staticmethod
    def _deduplicar(candidatas: list[FuenteCandidata]) -> list[FuenteCandidata]:
        vistas: set[str] = set()
        unicas = []
        for c in candidatas:
            claves = {f"url:{sha256_hex(c.url)}", f"titulo:{normalizar_para_comparar(c.titulo)}"}
            claves |= {f"doi:{c.doi.lower()}"} if c.doi else set()
            if not claves & vistas:
                unicas.append(c)
            vistas |= claves
        return unicas

    @staticmethod
    def _relevancia(candidata: FuenteCandidata, terminos: set[str]) -> int:
        texto = normalizar_para_comparar(f"{candidata.titulo} {candidata.extracto}")
        return sum(1 for t in terminos if t in texto)

    def _ordenar(self, candidatas: list[FuenteCandidata], consulta: str) -> list[FuenteCandidata]:
        terminos = {
            t for t in normalizar_para_comparar(consulta).split() if len(t) >= LONGITUD_MIN_TERMINO
        }
        return sorted(
            candidatas,
            key=lambda c: (
                c.autoridad,
                self._relevancia(c, terminos),
                c.fecha_publicacion.toordinal() if c.fecha_publicacion else 0,
            ),
            reverse=True,
        )

    def _seleccionar(
        self, ordenadas: list[FuenteCandidata], contexto: ContextoFuentes
    ) -> list[FuenteCandidata]:
        """La mejor de cada categoría primero (diversidad), luego el resto por orden."""
        primeras: dict[CategoriaFuente, FuenteCandidata] = {}
        for c in ordenadas:
            primeras.setdefault(c.categoria, c)
        resto = [c for c in ordenadas if c not in primeras.values()]
        elegidas = sorted(primeras.values(), key=ordenadas.index) + resto
        return elegidas[: self._settings.fuentes_max_por_turno]

    def _curadas(self, consulta: str) -> list[Fuente]:
        return self.permitidas(
            self._fuentes.buscar_curadas(consulta, self._settings.fuentes_max_por_turno)
        )

    def _materializar(self, candidatas: list[FuenteCandidata]) -> list[Fuente]:
        hashes = {sha256_hex(c.url): c for c in candidatas}
        guardadas = self.permitidas(self._fuentes.listar_por_url_hashes(list(hashes)))
        existentes = {f.url_hash: f for f in guardadas}
        pendientes = {f.url_hash: f for f in self._pendientes.values()}
        return [
            self._reutilizar(existentes.get(h), c) or pendientes.get(h) or self._nueva(h, c)
            for h, c in hashes.items()
        ]

    def _reutilizar(self, existente: Fuente | None, candidata: FuenteCandidata) -> Fuente | None:
        # Un registro vencido se reutiliza y se refresca al persistir, no antes de llamar al LLM.
        if existente is not None and existente.fecha_expiracion < ahora_utc():
            self._refrescos[existente.id_fuente] = (existente, candidata)
        return existente

    def _refrescar(self, fuente: Fuente, c: FuenteCandidata) -> None:
        ahora = ahora_utc()
        fuente.titulo = limpiar_texto_externo(c.titulo, MAX_TITULO)
        fuente.extracto = limpiar_texto_externo(
            c.extracto, self._settings.fuentes_extracto_max_caracteres
        )
        fuente.autoridad = c.autoridad
        fuente.fecha_consulta = ahora
        fuente.fecha_expiracion = ahora + timedelta(days=self._settings.fuentes_cache_dias)

    def _nueva(self, url_hash: str, c: FuenteCandidata) -> Fuente:
        ahora = ahora_utc()
        fuente = Fuente(
            id_fuente=uuid.uuid4(),
            tipo=TipoFuente.TEXTO,
            titulo=limpiar_texto_externo(c.titulo, MAX_TITULO),
            autor=limpiar_texto_externo(c.autor, MAX_AUTOR) or None,
            sitio=limpiar_texto_externo(c.sitio, MAX_SITIO),
            url=c.url,
            url_hash=url_hash,
            fecha_publicacion=c.fecha_publicacion,
            fecha_consulta=ahora,
            licencia=limpiar_texto_externo(c.licencia, MAX_LICENCIA) or None,
            extracto=limpiar_texto_externo(
                c.extracto, self._settings.fuentes_extracto_max_caracteres
            ),
            categoria=c.categoria,
            autoridad=c.autoridad,
            proveedor=c.proveedor[:40],
            doi=(c.doi or "")[:MAX_DOI] or None,
            revisada_por_pares=c.revisada_por_pares,
            idioma=(c.idioma or self._settings.fuentes_idiomas[0])[:LONGITUD_IDIOMA],
            fecha_expiracion=ahora + timedelta(days=self._settings.fuentes_cache_dias),
        )
        self._pendientes[fuente.id_fuente] = fuente
        return fuente
