import dataclasses
from datetime import date, timedelta
from typing import Any

from app.core.tiempo import ahora_utc
from app.core.unit_of_work import FabricaUnitOfWork
from app.crypto.indice_ciego import sha256_hex
from app.fuentes.base import FuenteCandidata
from app.models.cache_fuentes import CacheFuentes
from app.models.enums import CategoriaFuente
from app.repositories.cache_fuentes import CacheFuentesRepository
from app.validators.texto import normalizar_para_comparar


def normalizar_tema(tema: str) -> str:
    """Minúsculas, sin tildes ni espacios sobrantes: «Fotosíntesis » y «fotosintesis» coinciden."""
    return normalizar_para_comparar(tema).strip()


def _a_dict(candidata: FuenteCandidata) -> dict[str, Any]:
    datos = dataclasses.asdict(candidata)
    datos["categoria"] = candidata.categoria.value
    fecha = candidata.fecha_publicacion
    datos["fecha_publicacion"] = fecha.isoformat() if fecha else None
    return datos


def _desde_dict(datos: dict[str, Any]) -> FuenteCandidata:
    fecha = datos.get("fecha_publicacion")
    return FuenteCandidata(
        **{
            **datos,
            "categoria": CategoriaFuente(datos["categoria"]),
            "fecha_publicacion": date.fromisoformat(fecha) if fecha else None,
        }
    )


class CacheBusquedaFuentes:
    """Caché de resultados por proveedor y tema (FUENTES_CACHE_HORAS). Usa transacciones propias
    y cortas: un acierto evita llamar al proveedor aunque el caso de uso falle después. Solo se
    guardan resultados con fuentes; los errores y los vacíos nunca se cachean."""

    def __init__(self, fabrica_uow: FabricaUnitOfWork, horas: int) -> None:
        self._fabrica_uow = fabrica_uow
        self._vigencia = timedelta(hours=horas)

    @staticmethod
    def clave(proveedor: str, idioma: str, tema: str) -> str:
        return sha256_hex(f"{proveedor}|{idioma}|{normalizar_tema(tema)}")

    def leer(
        self, proveedores: list[str], idioma: str, tema: str
    ) -> dict[str, list[FuenteCandidata]]:
        if not proveedores or self._vigencia <= timedelta(0):
            return {}
        claves = {self.clave(p, idioma, tema): p for p in proveedores}
        with self._fabrica_uow.abrir() as uow:
            filas = CacheFuentesRepository(uow.session).listar_vigentes(list(claves), ahora_utc())
            return {claves[f.clave_hash]: [_desde_dict(c) for c in f.candidatas] for f in filas}

    def guardar(self, idioma: str, tema: str, resultados: dict[str, list[FuenteCandidata]]) -> None:
        con_fuentes = {p: lista for p, lista in resultados.items() if lista}
        if not con_fuentes or self._vigencia <= timedelta(0):
            return
        ahora = ahora_utc()
        with self._fabrica_uow.abrir() as uow:
            repositorio = CacheFuentesRepository(uow.session)
            for proveedor, lista in con_fuentes.items():
                repositorio.guardar(
                    CacheFuentes(
                        clave_hash=self.clave(proveedor, idioma, tema),
                        proveedor=proveedor[:40],
                        candidatas=[_a_dict(c) for c in lista],
                        fecha_creacion=ahora,
                        fecha_expiracion=ahora + self._vigencia,
                    )
                )
            uow.commit()
