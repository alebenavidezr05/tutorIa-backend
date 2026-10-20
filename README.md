# TutorIA — backend

API de FastAPI para TutorIA: diagnóstico, plan de estudio y el tutor conversacional **Vex**
(Claude), con fuentes verificables, recursos visuales, autorización de menores, cifrado de datos
personales y derechos del titular (Ley 1581). Este es un resumen; el README completo del
proyecto (despliegue en AWS, `docker compose`) está en la raíz del repositorio (prompt 03).

## Requisitos

- Python 3.11 (también probado con 3.14) y PostgreSQL 15+ (en desarrollo sirve SQLite).
- Las dependencias se instalan solo con paquetes precompilados en Windows, Linux (x86_64/aarch64)
  y macOS (Intel y Apple Silicon).

## Puesta en marcha

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # en Windows: copy .env.example .env
python -m app.scripts.generar_clave_local   # pega los valores en .env (solo desarrollo)
uvicorn app.main:app --reload
```

Las tablas se crean al arrancar (`create_all` bajo un candado consultivo de PostgreSQL).
Documentación interactiva: `http://localhost:8000/docs` (desactivada en producción).

Para trabajar **sin red ni llaves**, deja en `fake` los proveedores (`LLM_PROVIDER`,
`MODERACION_PROVEEDOR`, `VIDEOS_PROVEEDOR`, `CORREO_PROVEEDOR`…) y borra `FUENTES_PROVEEDORES` /
`IMAGENES_PROVEEDORES` del `.env` (sus valores por defecto son simulados).

## Pruebas y calidad

```bash
pytest --cov=app/services --cov=app/validators
ruff check . && ruff format --check .
mypy app
```

Por defecto las pruebas usan SQLite en un directorio temporal. Para PostgreSQL real (CI):
`TEST_DATABASE_URL=postgresql+psycopg://...` (activa también las pruebas marcadas `db`).

## Conectar Claude

1. Crea una llave en la consola de Anthropic (cuenta comercial de API).
2. En `.env`: `LLM_PROVIDER=anthropic`, `LLM_API_KEY=...`, `LLM_MODEL_SENCILLO=claude-haiku-5-5`,
   `LLM_MODEL_COMPLEJO=claude-sonnet-5-5`.
3. `python -m app.scripts.probar_llm`: imprime modelo, latencia y tokens de cada modelo y
   distingue llave inválida, modelo no disponible y falta de conexión (nunca muestra la llave).

El resto de proveedores se verifica con `python -m app.scripts.probar_proveedores` (no genera
imágenes de pago ni envía correos).

## Scripts (`python -m app.scripts.<nombre>`)

| Script | Uso |
|---|---|
| `reiniciar_tablas` | Borra y recrea las tablas (se niega en producción). |
| `probar_llm` · `probar_proveedores` | Diagnóstico de conexiones. |
| `generar_clave_local` | Claves aleatorias para desarrollo. |
| `generar_dek_kms --kms-key-id <id>` | DEK envuelta con KMS para `CIFRADO_DEK_ENVUELTA`. |
| `rotar_cifrado` | Re-cifra columnas con la versión de clave actual (idempotente). |
| `cargar_fuentes_curadas <json>` · `cargar_videos <json>` | Catálogos revisados por personas (ejemplos en `data/`). |
| `refrescar_metadatos_video` | Política de 30 días de YouTube; retira videos que ya no cumplen. |
| `limpiar_datos_vencidos` | Retención: archivos, conversaciones, alertas, consumos, copias e hilos huérfanos. |
| `listar_alertas [--detalle]` · `listar_solicitudes_vencidas` | Revisión humana. |

## Arquitectura

`routers` (sin lógica) → `services` (casos de uso) → `repositories` (solo consultas) → PostgreSQL.
Los proveedores externos están detrás de interfaces (`llm`, `moderacion`, `fuentes`, `imagenes`,
`videos`, `almacen`, `correo`, `pagos`, `crypto`) con un adaptador real y uno simulado.
Toda ruta exige sesión salvo la lista cerrada `RUTAS_PUBLICAS` (`app/core/seguridad.py`);
`tests/api/test_seguridad_acceso.py` falla si aparece una ruta sin protección.

Proveedores de fuentes e imágenes elegidos y su estado: [`docs/fuentes.md`](docs/fuentes.md).

## Límites conocidos (documentados con honestidad)

- **Citas**: el backend comprueba que cada hecho cite una fuente recuperada en la conversación y
  con la autoridad mínima, no que el extracto respalde semánticamente cada frase.
- **Videos**: el sistema no ve el video; solo conoce título, canal, duración y puntos clave
  aprobados por una persona.
- **Edad y representación legal** son declaraciones; el correo verificado prueba control del
  buzón, no identidad.
- **Cifrado**: protege la base de datos; no cubre datos en memoria ni lo enviado a los
  proveedores de IA. El texto libre puede contener datos que el estudiante escriba: se redactan
  correos, teléfonos y documentos antes de guardar y de enviar.
- **Pagos**: solo existe la pasarela simulada; producción exige un adaptador real.

## Revisión legal pendiente (antes del lanzamiento comercial)

- Tratamiento de datos de menores y autorización del representante legal (Ley 1581 de 2012,
  art. 7; Decreto 1377 de 2013 compilado en el Decreto 1074 de 2015).
- Transferencia internacional a EE. UU. (Anthropic, OpenAI, AWS) y contratos con cada encargado;
  verificar en cada cuenta que los datos no se usen para entrenar modelos.
- Política de tratamiento y textos de autorización: `app/legal/` son **plantillas** que un
  abogado debe revisar y completar; en producción la app no arranca con marcadores `{{...}}`.
- Plazos de consulta (10) y reclamo (15 días hábiles) y lista anual de festivos (`FESTIVOS_CO`).
- Verificar si la organización debe inscribirse en el Registro Nacional de Bases de Datos.
- Procedimiento de incidentes: contener, evaluar el alcance, notificar a la SIC dentro del plazo
  vigente y a los titulares afectados, y documentar.
- La «Resolución 2654 de 2019» citada en el Plan de Negocios **no se pudo confirmar**.
- Las líneas de ayuda (141 ICBF, 123) y los textos fijos de seguridad requieren revisión humana.
