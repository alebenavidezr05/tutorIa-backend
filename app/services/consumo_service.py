import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import Settings, TarifaModelo
from app.core.tiempo import ahora_utc, inicio_de_mes_utc
from app.core.unit_of_work import FabricaUnitOfWork
from app.exceptions.base import LimiteUsoError
from app.llm.base import LLMRespuesta
from app.models.consumo_ia import ConsumoIA
from app.models.enums import OperacionIA, ProveedorIA
from app.repositories.uso import ConsumoIARepository

TOKENS_POR_MILLON = Decimal(1_000_000)
DECIMALES_COSTO = Decimal("0.000001")


@dataclass(frozen=True)
class UsoTokens:
    entrada: int = 0
    salida: int = 0
    cache_lectura: int = 0
    cache_escritura: int = 0


def _costo_tokens(uso: UsoTokens, tarifa: TarifaModelo) -> Decimal:
    total = (
        Decimal(uso.entrada) * Decimal(str(tarifa.entrada))
        + Decimal(uso.salida) * Decimal(str(tarifa.salida))
        + Decimal(uso.cache_lectura) * Decimal(str(tarifa.cache_lectura))
        + Decimal(uso.cache_escritura) * Decimal(str(tarifa.cache_escritura))
    )
    return (total / TOKENS_POR_MILLON).quantize(DECIMALES_COSTO)


class ConsumoService:
    """Libro de costos de IA. Confirma en su propia transacción: el dinero ya se gastó aunque el
    caso de uso que lo provocó falle después (única excepción a «un commit por caso de uso»)."""

    def __init__(self, fabrica_uow: FabricaUnitOfWork, settings: Settings) -> None:
        self._fabrica_uow = fabrica_uow
        self._settings = settings

    def registrar_llm(
        self, id_usuario: uuid.UUID | None, operacion: OperacionIA, respuesta: LLMRespuesta
    ) -> None:
        uso = UsoTokens(
            respuesta.tokens_entrada,
            respuesta.tokens_salida,
            respuesta.tokens_cache_lectura,
            respuesta.tokens_cache_escritura,
        )
        self.registrar(
            id_usuario, ProveedorIA.ANTHROPIC, respuesta.modelo, operacion, uso, imagenes=0
        )

    def registrar_imagen(
        self, id_usuario: uuid.UUID, modelo: str, uso: UsoTokens | None, exito: bool
    ) -> None:
        self.registrar(
            id_usuario, ProveedorIA.OPENAI, modelo, OperacionIA.IMAGEN, uso or UsoTokens(), 1, exito
        )

    def registrar(
        self,
        id_usuario: uuid.UUID | None,
        proveedor: ProveedorIA,
        modelo: str,
        operacion: OperacionIA,
        uso: UsoTokens,
        imagenes: int,
        exito: bool = True,
    ) -> None:
        costo, es_estimacion = self._costo(modelo, uso, imagenes)
        with self._fabrica_uow.abrir() as uow:
            ConsumoIARepository(uow.session).agregar(
                ConsumoIA(
                    id_usuario=id_usuario,
                    proveedor=proveedor,
                    modelo=modelo[:60],
                    operacion=operacion,
                    tokens_entrada=uso.entrada,
                    tokens_salida=uso.salida,
                    tokens_cache_lectura=uso.cache_lectura,
                    tokens_cache_escritura=uso.cache_escritura,
                    imagenes=imagenes,
                    costo_estimado_usd=costo,
                    es_estimacion=es_estimacion,
                    exito=exito,
                    fecha=ahora_utc(),
                )
            )
            uow.commit()

    def costo_mensual(self, operacion: OperacionIA) -> Decimal:
        with self._fabrica_uow.abrir() as uow:
            return ConsumoIARepository(uow.session).sumar_costo(operacion, inicio_de_mes_utc())

    def asegurar_presupuesto_imagenes(self) -> None:
        tope = Decimal(str(self._settings.presupuesto_imagenes_mensual_usd))
        if self.costo_mensual(OperacionIA.IMAGEN) >= tope:
            raise LimiteUsoError("Se alcanzó el presupuesto mensual de ilustraciones.")

    def _costo(self, modelo: str, uso: UsoTokens, imagenes: int) -> tuple[Decimal, bool]:
        tarifa = self._settings.tarifas_ia.get(modelo)
        tiene_tokens = (uso.entrada + uso.salida) > 0
        if tarifa is not None and tiene_tokens:
            return _costo_tokens(uso, tarifa), False
        if imagenes:
            # Sin uso informado por la API se registra una estimación, marcada como tal.
            estimado = Decimal(str(self._settings.imagenes_ia_costo_estimado_usd)) * imagenes
            return estimado.quantize(DECIMALES_COSTO), True
        return Decimal(0), True
