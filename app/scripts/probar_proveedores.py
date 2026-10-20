"""Verifica moderación, fuentes, imágenes, YouTube, S3, KMS y SES sin gastar en imágenes IA."""

import sys
import uuid
from collections.abc import Callable
from functools import partial

from app.core.contenedor import Contenedor
from app.exceptions.base import AppError
from app.fuentes.base import FuentesClient
from app.imagenes.base import ImagenesClient
from app.scripts._comun import contenedor_de_script

TEMA_PRUEBA = "fotosíntesis"
VIDEO_PRUEBA = "dQw4w9WgXcQ"


def _verificar(nombre: str, prueba: Callable[[], str]) -> bool:
    try:
        print(f"[OK] {nombre}: {prueba()}")
        return True
    except AppError as exc:
        print(f"[FALLA] {nombre}: {exc.codigo}")
        return False


def _pruebas(contenedor: Contenedor) -> list[tuple[str, Callable[[], str]]]:
    s = contenedor.settings
    pruebas: list[tuple[str, Callable[[], str]]] = [
        (
            "moderación",
            lambda: f"disponible={contenedor.moderador.moderar_texto('hola').disponible}",
        ),
    ]
    idioma = s.fuentes_idiomas[0]
    pruebas += [
        (f"fuentes/{f.proveedor}", partial(_probar_fuente, f, idioma)) for f in contenedor.fuentes
    ]
    pruebas += [
        (f"imágenes/{i.proveedor}", partial(_probar_imagenes, i)) for i in contenedor.imagenes
    ]
    if s.videos_proveedor == "youtube":
        pruebas.append(
            (
                "youtube",
                lambda: f"{len(contenedor.videos.obtener_metadatos([VIDEO_PRUEBA]))} videos",
            )
        )
    if s.almacen_proveedor == "s3":
        pruebas.append(("s3", lambda: _probar_almacen(contenedor)))
    return pruebas


def _probar_fuente(proveedor: FuentesClient, idioma: str) -> str:
    return f"{len(proveedor.buscar(TEMA_PRUEBA, idioma, 2))} resultados"


def _probar_imagenes(proveedor: ImagenesClient) -> str:
    return f"{len(proveedor.buscar(TEMA_PRUEBA, 2))} resultados"


def _probar_almacen(contenedor: Contenedor) -> str:
    clave = f"pruebas/{uuid.uuid4()}"
    contenedor.almacen.guardar(clave, b"ok", "text/plain")
    contenido = contenedor.almacen.leer(clave)
    contenedor.almacen.eliminar(clave)
    return f"lectura={contenido == b'ok'}"


def main() -> int:
    # KMS se verifica al construir el contenedor (descifra la DEK); SES no se prueba para no
    # enviar correos reales: basta con revisar la identidad verificada en la consola de AWS.
    with contenedor_de_script(crear=False) as contenedor:
        resultados = [_verificar(nombre, prueba) for nombre, prueba in _pruebas(contenedor)]
        print(f"[OK] cifrado: proveedor={contenedor.settings.cifrado_proveedor}")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
