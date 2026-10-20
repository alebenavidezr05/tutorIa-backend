"""Solicitudes de titulares (Ley 1581) cuyo plazo vence pronto o ya venció.

Uso: python -m app.scripts.listar_solicitudes_vencidas [--dias 3]
"""

import argparse
import sys
from datetime import timedelta

from app.core.tiempo import hoy_utc
from app.scripts._comun import servicios_de_script

DIAS_ANTICIPACION = 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dias", type=int, default=DIAS_ANTICIPACION)
    hasta = hoy_utc() + timedelta(days=parser.parse_args().dias)
    with servicios_de_script() as f:
        solicitudes = f.privacidad.listar_por_vencer(hasta)
        for s in solicitudes:
            estado = "VENCIDA" if s.fecha_limite < hoy_utc() else "POR VENCER"
            print(
                f"[{estado}] {s.id_solicitud} {s.tipo.value} límite={s.fecha_limite} estado={s.estado.value}"
            )
    print(f"{len(solicitudes)} solicitudes requieren respuesta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
