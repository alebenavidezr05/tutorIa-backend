# syntax=docker/dockerfile:1
# Imagen del backend de TutorIA (Python 3.11, multi-arquitectura: x86_64 y ARM64).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencias primero: la capa se reutiliza mientras requirements.txt no cambie.
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary=:all: -r requirements.txt

COPY app ./app
# Ejemplos de contenido curado (cargar_fuentes_curadas / cargar_videos).
COPY data ./data

# Usuario sin privilegios. /data/archivos es el único directorio escribible
# (almacén local de archivos, solo con ALMACEN_PROVEEDOR=local; en producción se usa S3).
RUN useradd --create-home --uid 10001 tutoria \
    && mkdir -p /data/archivos \
    && chown -R tutoria /data/archivos
USER tutoria

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"

# --proxy-headers: la IP real llega de Caddy en X-Forwarded-For (límite de intentos de login).
# --forwarded-allow-ips "*" es aceptable SOLO porque el backend no publica puertos: su único
# cliente posible es Caddy por la red interna de Docker. Sin --reload (va en docker-compose.dev.yml).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
