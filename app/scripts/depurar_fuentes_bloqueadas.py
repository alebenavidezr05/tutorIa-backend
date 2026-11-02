"""Informa (y con --aplicar depura) las filas de `fuente` cuyo dominio está bloqueado.

Uso: python -m app.scripts.depurar_fuentes_bloqueadas [--aplicar]

Sin --aplicar no borra nada: solo cuenta las filas bloqueadas y cuántas están referenciadas por
mensajes, planes o preguntas de diagnóstico. Con --aplicar borra las no referenciadas y lista las
referenciadas para que una persona decida (la lectura ya las filtra: nunca llegan al modelo).
"""

import argparse
import sys
import uuid
from dataclasses import dataclass, field

from app.fuentes.bloqueo import es_dominio_bloqueado, normalizar_host
from app.repositories.fuente import FuenteRepository
from app.scripts._comun import servicios_de_script


@dataclass
class Diagnostico:
    bloqueadas: dict[uuid.UUID, str] = field(default_factory=dict)
    referencias: dict[uuid.UUID, list[str]] = field(default_factory=dict)

    @property
    def no_referenciadas(self) -> list[uuid.UUID]:
        return [i for i in self.bloqueadas if i not in self.referencias]


def diagnosticar(repo: FuenteRepository, dominios_bloqueados: list[str]) -> Diagnostico:
    diagnostico = Diagnostico(
        bloqueadas={
            id_fuente: normalizar_host(url) or "(url inválida)"
            for id_fuente, url in repo.listar_id_y_url()
            if es_dominio_bloqueado(url, dominios_bloqueados)
        }
    )
    ids = list(diagnostico.bloqueadas)
    usos = {
        "mensajes": repo.ids_en_mensajes(ids),
        "planes": repo.ids_en_planes(ids),
        "diagnósticos": repo.ids_en_diagnosticos(ids),
    }
    for tipo, referenciadas in usos.items():
        for id_fuente in referenciadas:
            diagnostico.referencias.setdefault(id_fuente, []).append(tipo)
    return diagnostico


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aplicar", action="store_true", help="borra las no referenciadas")
    aplicar = parser.parse_args().aplicar
    with servicios_de_script() as f:
        diagnostico = diagnosticar(f.fuentes_repo, f.settings.fuentes_dominios_bloqueados)
        borrables = diagnostico.no_referenciadas
        print(f"Fuentes con dominio bloqueado: {len(diagnostico.bloqueadas)}")
        print(f"Referenciadas (mensajes, planes o diagnósticos): {len(diagnostico.referencias)}")
        print(f"No referenciadas: {len(borrables)}")
        if not aplicar:
            print("Modo informe: no se borró nada. Usa --aplicar para depurar.")
            return 0
        if borrables:
            f.fuentes_repo.eliminar_por_ids(borrables)
            f.uow.commit()
        print(f"Borradas: {len(borrables)}")
        for id_fuente, tipos in diagnostico.referencias.items():
            host = diagnostico.bloqueadas[id_fuente]
            print(f"  revisar {id_fuente} {host} usada en: {', '.join(sorted(tipos))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
