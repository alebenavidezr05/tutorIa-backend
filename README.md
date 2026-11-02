# TutorIA — backend

API de FastAPI para TutorIA: diagnóstico, plan de estudio y el tutor conversacional **Vex**
(Claude), con fuentes verificables, recursos visuales, autorización de menores, cifrado de datos
personales y derechos del titular (Ley 1581). Arquitectura: `routers` (sin lógica) → `services`
→ `repositories` → PostgreSQL; cada proveedor externo tiene un adaptador real y uno simulado.

**El README completo (despliegue en EC2, `docker compose`, scripts, límites conocidos y revisión
legal pendiente) está en el repositorio `tutorIa-compose`.**

## Ejecutar en local

Requisitos: Python 3.11+ y PostgreSQL 15+ (en desarrollo también sirve SQLite).

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # en Windows: copy .env.example .env
python -m app.scripts.generar_clave_local   # pega los valores en .env (solo desarrollo)
uvicorn app.main:app --reload
```

Documentación interactiva en `http://localhost:8000/docs` (desactivada en producción). Para
trabajar sin red ni llaves, deja los proveedores en `fake` y borra `FUENTES_PROVEEDORES` /
`IMAGENES_PROVEEDORES` del `.env`.

Variables de fuentes a conocer (detalle en [`docs/fuentes.md`](docs/fuentes.md)):
`FUENTES_PROVEEDORES` (por defecto OpenAlex y MedlinePlus en español; nunca sitios editables por
cualquiera: la app no arranca si se configura uno), `FUENTES_DOMINIOS_BLOQUEADOS` (amplía la lista
base de dominios excluidos, nunca la reduce) y `PRENSA_RESPALDA_SOLA` (por defecto `false`).

## Pruebas

```bash
pytest --cov=app/services --cov=app/validators
ruff check . && ruff format --check .
mypy app
```

Por defecto las pruebas usan SQLite temporal; con `TEST_DATABASE_URL=postgresql+psycopg://...`
corren contra PostgreSQL real (y se activan las marcadas `db`).

## Seguridad en tránsito

TLS en el borde (el servidor web del despliegue en EC2, o CloudFront/ALB en una arquitectura
administrada). La base de datos va en una red interna de Docker sin salida a internet, o con
`sslmode=require` si fuera un servicio administrado. La cookie de sesión es `httpOnly`,
`SameSite=Lax` y `Secure` fuera de desarrollo; `COOKIE_DOMAIN` queda vacío porque frontend y API
comparten origen.
