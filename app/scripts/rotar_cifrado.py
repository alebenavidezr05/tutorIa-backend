"""Re-cifra las columnas cifradas con la versión actual de la clave.

Pasos: 1) agrega la clave/DEK nueva y mueve la anterior a CIFRADO_CLAVES_ANTERIORES con su
versión; 2) sube CIFRADO_VERSION_ACTUAL; 3) ejecuta este script. Es idempotente: los valores que
ya tienen el prefijo de la versión actual no se tocan.
"""

import sys
from typing import Any

from sqlalchemy import Table, Text, select, type_coerce, update

from app.core.database import Base
from app.crypto.registro import registro_cifrador
from app.crypto.tipos import FechaCifrada, JsonCifrado, TextoCifrado
from app.scripts._comun import contenedor_de_script

TIPOS_CIFRADOS = (TextoCifrado, JsonCifrado, FechaCifrada)


def _columnas_cifradas(tabla: Table) -> list[Any]:
    return [c for c in tabla.columns if isinstance(c.type, TIPOS_CIFRADOS)]


def _rotar_columna(conexion: Any, tabla: Table, columna: Any) -> int:
    cifrador = registro_cifrador.obtener()
    clave_primaria = list(tabla.primary_key.columns)
    crudo = type_coerce(columna, Text)
    filas = conexion.execute(
        select(*clave_primaria, crudo.label("valor")).where(columna.is_not(None))
    ).all()
    rotadas = 0
    for fila in filas:
        if cifrador.es_version_actual(fila.valor):
            continue
        texto = cifrador.descifrar(fila.valor, columna.type.aad)
        condicion = [c == getattr(fila, c.name) for c in clave_primaria]
        conexion.execute(
            update(tabla)
            .where(*condicion)
            .values({columna.name: type_coerce(cifrador.cifrar(texto, columna.type.aad), Text)})
        )
        rotadas += 1
    return rotadas


def main() -> int:
    import app.models  # noqa: F401  (registra las entidades)

    with contenedor_de_script(crear=False) as contenedor, contenedor.engine.begin() as conexion:
        for tabla in Base.metadata.sorted_tables:
            for columna in _columnas_cifradas(tabla):
                print(
                    f"{tabla.name}.{columna.name}: {_rotar_columna(conexion, tabla, columna)} valores re-cifrados"
                )
    return 0


if __name__ == "__main__":
    sys.exit(main())
