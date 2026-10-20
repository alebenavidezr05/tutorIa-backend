"""Retención: borra archivos, conversaciones, alertas, consumos y copias de imágenes vencidos,
vence tokens de autorización pendientes y marca como fallidos los trabajos visuales huérfanos."""

import sys

from app.scripts._comun import servicios_de_script


def main() -> int:
    with servicios_de_script() as f:
        resumen = f.retencion.limpiar()
        huerfanos = f.trabajo_visual.recuperar_huerfanos()
    for campo, valor in vars(resumen).items():
        print(f"{campo}: {valor}")
    print(f"trabajos_huerfanos: {huerfanos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
