"""Alertas de seguridad abiertas para revisión humana. El detalle solo se muestra con --detalle."""

import argparse
import sys

from app.scripts._comun import servicios_de_script


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detalle", action="store_true", help="muestra el texto descifrado")
    mostrar_detalle = parser.parse_args().detalle
    with servicios_de_script() as f:
        alertas = f.alertas_repo.listar_abiertas()
        for a in alertas:
            detalle = f" detalle={a.detalle!r}" if mostrar_detalle and a.detalle else ""
            print(
                f"{a.fecha:%Y-%m-%d %H:%M} {a.id_alerta} {a.origen.value} {a.categoria.value} usuario={a.id_usuario}{detalle}"
            )
    print(f"{len(alertas)} alertas abiertas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
