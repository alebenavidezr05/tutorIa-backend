"""Reglas de arquitectura verificadas sobre el AST del código (§2 y §20)."""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "app"
# Únicos lugares con try/except permitidos (§2.6): adaptadores, parser y los dos casos de services.
TRY_PERMITIDOS = {
    "llm/anthropic_client.py",
    "llm/parser.py",
    "moderacion/openai_moderacion_client.py",
    "moderacion/tolerante.py",
    "imagenes/openai_imagenes_client.py",
    "imagenes/adaptadores/http.py",
    "imagenes/descarga_segura.py",
    "imagenes/procesador.py",
    "imagenes/base.py",
    "fuentes/adaptadores/http.py",
    "videos/youtube_client.py",
    "videos/tolerante.py",
    "almacen/s3_almacen.py",
    "almacen/base.py",
    "correo/ses_correo_client.py",
    # Valida direcciones y envía sin propagar fallos: el registro no falla si el correo no sale.
    "correo/tolerante.py",
    "crypto/kms_cifrador.py",
    "crypto/base.py",
    "crypto/jwt_firmador.py",
    "services/tutor/consolidacion_service.py",
    "services/visual/trabajo_visual_service.py",
    # CLI de diagnóstico: su propósito es sondear proveedores externos e informar cada fallo.
    "scripts/probar_proveedores.py",
}
NODOS_CON_LOGICA = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.IfExp)


def _archivos(carpeta: str) -> list[Path]:
    return sorted((RAIZ / carpeta).rglob("*.py"))


def _arbol(ruta: Path) -> ast.Module:
    return ast.parse(ruta.read_text(encoding="utf-8"))


def _relativa(ruta: Path) -> str:
    return ruta.relative_to(RAIZ).as_posix()


def _importaciones(arbol: ast.Module) -> set[str]:
    modulos: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos |= {a.name for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.add(nodo.module)
    return modulos


def test_routers_sin_logica_y_un_solo_service() -> None:
    for ruta in _archivos("routers"):
        for funcion in (n for n in ast.walk(_arbol(ruta)) if isinstance(n, ast.FunctionDef)):
            nodos = list(ast.walk(funcion))
            assert not any(isinstance(n, NODOS_CON_LOGICA) for n in nodos), (
                f"{ruta.name}:{funcion.name}"
            )
            assert not any(isinstance(n, ast.comprehension) for n in nodos), (
                f"{ruta.name}:{funcion.name}"
            )
            llamadas = [
                n
                for n in nodos
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "servicio"
            ]
            assert len(llamadas) <= 1, f"{ruta.name}:{funcion.name} llama más de un service"


def test_routers_no_acceden_a_repositorios() -> None:
    for ruta in _archivos("routers"):
        assert not any(m.startswith("app.repositories") for m in _importaciones(_arbol(ruta))), (
            ruta.name
        )


def test_repositorios_sin_commit_ni_raise_ni_condicionales() -> None:
    for ruta in _archivos("repositories"):
        arbol = _arbol(ruta)
        nombres = {n.attr for n in ast.walk(arbol) if isinstance(n, ast.Attribute)}
        assert "commit" not in nombres, ruta.name
        assert not any(isinstance(n, (ast.Raise, ast.If, ast.Try)) for n in ast.walk(arbol)), (
            ruta.name
        )


def test_services_no_importan_fastapi() -> None:
    for ruta in _archivos("services"):
        importados = _importaciones(_arbol(ruta))
        assert not any(m == "fastapi" or m.startswith("fastapi.") for m in importados), ruta.name
        assert not any(m.startswith("starlette") for m in importados), ruta.name


def test_try_except_solo_en_fronteras_permitidas() -> None:
    for ruta in RAIZ.rglob("*.py"):
        tiene_try = any(isinstance(n, ast.Try) for n in ast.walk(_arbol(ruta)))
        if tiene_try:
            assert _relativa(ruta) in TRY_PERMITIDOS, (
                f"try/except no permitido en {_relativa(ruta)}"
            )


def test_sin_except_pass_ni_http_exception() -> None:
    for ruta in RAIZ.rglob("*.py"):
        arbol = _arbol(ruta)
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ExceptHandler):
                assert not (len(nodo.body) == 1 and isinstance(nodo.body[0], ast.Pass)), _relativa(
                    ruta
                )
        texto = ruta.read_text(encoding="utf-8")
        if _relativa(ruta) != "exceptions/handlers.py":
            assert "raise HTTPException" not in texto, _relativa(ruta)


def test_patrones_de_entrega_directa_tienen_una_sola_fuente() -> None:
    for ruta in RAIZ.rglob("*.py"):
        if _relativa(ruta) == "validators/entrega_directa.py":
            continue
        assert "la respuesta (correcta )?es" not in ruta.read_text(encoding="utf-8"), _relativa(
            ruta
        )


def test_variables_de_entorno_solo_en_settings() -> None:
    for ruta in RAIZ.rglob("*.py"):
        texto = ruta.read_text(encoding="utf-8")
        assert "os.environ" not in texto and "os.getenv" not in texto, _relativa(ruta)


def test_calidad_de_imagen_no_es_configurable() -> None:
    config = (RAIZ / "core" / "config.py").read_text(encoding="utf-8")
    assert "calidad" not in config.lower()
    textos = [p.read_text(encoding="utf-8") for p in RAIZ.rglob("*.py")]
    lineas = [linea.strip() for t in textos for linea in t.splitlines() if "quality=" in linea]
    imagenes_ia = [linea for linea in lineas if "CALIDAD_WEBP" not in linea]
    assert imagenes_ia == ["quality=CALIDAD_IMAGEN_IA,"]


def test_sin_nombres_de_modelo_claude_en_el_codigo() -> None:
    for ruta in RAIZ.rglob("*.py"):
        assert "claude-" not in ruta.read_text(encoding="utf-8"), _relativa(ruta)
