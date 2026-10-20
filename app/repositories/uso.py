import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects import postgresql, sqlite

from app.models.consumo_ia import ConsumoIA
from app.models.enums import CampoUso, OperacionIA
from app.models.limite_frecuencia import LimiteFrecuencia
from app.models.tipos import nuevo_uuid
from app.models.uso_diario import UsoDiario
from app.repositories.base import RepositorioBase

_INSERT_POR_DIALECTO = {"postgresql": postgresql.insert, "sqlite": sqlite.insert}


class UsoDiarioRepository(RepositorioBase[UsoDiario]):
    modelo = UsoDiario

    def incrementar_si_hay_cupo(
        self, id_usuario: uuid.UUID, fecha: date, campo: CampoUso, limite: int
    ) -> bool:
        """UPDATE condicionado y atómico: dos peticiones simultáneas no pueden superar el límite."""
        self._crear_fila_del_dia(id_usuario, fecha)
        columna = getattr(UsoDiario, campo.value)
        sentencia = (
            update(UsoDiario)
            .where(UsoDiario.id_usuario == id_usuario, UsoDiario.fecha == fecha, columna < limite)
            .values({columna: columna + 1})
            .returning(UsoDiario.id_uso)
        )
        return self._session.execute(sentencia).first() is not None

    def obtener(self, id_usuario: uuid.UUID, fecha: date) -> UsoDiario | None:
        consulta = select(UsoDiario).where(
            UsoDiario.id_usuario == id_usuario, UsoDiario.fecha == fecha
        )
        return self._session.scalar(consulta)

    def _crear_fila_del_dia(self, id_usuario: uuid.UUID, fecha: date) -> None:
        construir_insert: Any = _INSERT_POR_DIALECTO.get(
            self._session.get_bind().dialect.name, insert
        )
        sentencia = construir_insert(UsoDiario).values(
            id_uso=nuevo_uuid(),
            id_usuario=id_usuario,
            fecha=fecha,
            mensajes=0,
            planes=0,
            imagenes_ia=0,
            busquedas_video=0,
            archivos=0,
        )
        self._session.execute(
            sentencia.on_conflict_do_nothing(index_elements=["id_usuario", "fecha"])
        )


class ConsumoIARepository(RepositorioBase[ConsumoIA]):
    modelo = ConsumoIA

    def sumar_costo(self, operacion: OperacionIA, desde: datetime) -> Decimal:
        consulta = select(func.coalesce(func.sum(ConsumoIA.costo_estimado_usd), 0)).where(
            ConsumoIA.operacion == operacion, ConsumoIA.fecha >= desde
        )
        return Decimal(str(self._session.scalar(consulta) or 0))

    def eliminar_anteriores_a(self, instante: datetime) -> int:
        resultado = self._session.execute(delete(ConsumoIA).where(ConsumoIA.fecha < instante))
        return int(getattr(resultado, "rowcount", 0) or 0)


class LimiteFrecuenciaRepository(RepositorioBase[LimiteFrecuencia]):
    modelo = LimiteFrecuencia

    def obtener(self, clave_hash: str) -> LimiteFrecuencia | None:
        return self._session.get(LimiteFrecuencia, clave_hash)
