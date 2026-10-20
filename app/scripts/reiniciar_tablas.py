"""Borra y recrea todas las tablas. SOLO desarrollo: en producción se niega."""

from app.core.config import get_settings
from app.core.database import crear_tablas, eliminar_tablas
from app.exceptions.base import OperacionNoPermitidaError
from app.scripts._comun import contenedor_de_script


def main() -> None:
    settings = get_settings()
    if settings.es_produccion:
        raise OperacionNoPermitidaError("reiniciar_tablas no se puede ejecutar en producción.")
    with contenedor_de_script(settings, crear=False) as contenedor:
        eliminar_tablas(contenedor.engine)
        crear_tablas(contenedor.engine)
    print("Tablas recreadas.")


if __name__ == "__main__":
    main()
