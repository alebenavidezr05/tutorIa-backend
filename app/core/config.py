import re
from datetime import date
from functools import lru_cache
from typing import Literal, Self

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LONGITUD_MINIMA_SECRETO = 32
SECRETO_JWT_DESARROLLO = "solo-desarrollo-cambiar-este-secreto-jwt-0000"
CLAVE_INDICE_CIEGO_DESARROLLO = "solo-desarrollo-cambiar-clave-indice-ciego-0000"
# Clave AES de 32 bytes en base64, solo para desarrollo y pruebas; producción exige KMS.
CLAVE_LOCAL_DESARROLLO = "ZGVzYXJyb2xsby1zb2xvLWNsYXZlLWFlcy0zMmJ5dGU="
PROVEEDORES_FALSOS = {"fake", "local"}
PATRON_URL_CON_COMODIN = re.compile(r"\*")


class ConfigProveedor(BaseModel):
    """Proveedor de fuentes o imágenes abiertas declarado por configuración (§12.2–§12.3)."""

    id: str
    categoria: str
    adaptador: str
    activo: bool = True
    idiomas: list[str] = Field(default_factory=lambda: ["es"])
    base_url: str = ""
    requiere_llave: bool = False
    llave: SecretStr | None = None
    dominios: list[str] = Field(default_factory=list)
    autoridad: int | None = Field(default=None, ge=1, le=4)
    parametros: dict[str, str] = Field(default_factory=dict)


class TarifaModelo(BaseModel):
    """USD por millón de tokens; `imagen` es USD por imagen cuando la API no informa tokens."""

    entrada: float = 0.0
    salida: float = 0.0
    cache_lectura: float = 0.0
    cache_escritura: float = 0.0


class LineaAyuda(BaseModel):
    nombre: str
    numero: str


def _proveedores_fuentes_falsos() -> list[ConfigProveedor]:
    categorias = ("ACADEMICA_ABIERTA", "INSTITUCIONAL_OFICIAL", "EDUCATIVA_ABIERTA", "REFERENCIA")
    return [
        ConfigProveedor(id=f"fake_{c.lower()}", categoria=c, adaptador="fake") for c in categorias
    ]


def _proveedores_imagenes_falsos() -> list[ConfigProveedor]:
    return [
        ConfigProveedor(
            id="fake_imagenes",
            categoria="REPOSITORIO_COLABORATIVO",
            adaptador="fake",
            dominios=["imagenes.example.org"],
        )
    ]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # General y base de datos
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./tutoria_dev.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_sslmode: str = "prefer"

    # Sesión
    jwt_secret: SecretStr = SecretStr(SECRETO_JWT_DESARROLLO)
    jwt_expira_minutos: int = 1440
    cookie_nombre: str = "tutoria_sesion"
    cookie_domain: str | None = None
    cookie_secure: bool = False
    bcrypt_rounds: int = 12
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])
    frontend_url: str = "http://localhost:4200"
    rate_limit_login_intentos: int = 5
    rate_limit_login_ventana_minutos: int = 15

    # Edad y autorización del acudiente
    edad_minima: int = 13
    edad_mayoria: int = 18
    edad_maxima: int = 100
    autorizacion_token_horas: int = 72
    autorizacion_expira_dias: int = 365
    autorizacion_max_solicitudes_por_hora: int = 3

    # Correo
    correo_proveedor: Literal["fake", "smtp", "ses"] = "fake"
    correo_remitente: str = "no-responder@tutoria.local"
    ses_region: str = "us-east-1"
    smtp_host: str = "localhost"
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_contrasena: SecretStr = SecretStr("")
    smtp_tls: bool = True

    # Cifrado
    cifrado_proveedor: Literal["local", "kms"] = "local"
    cifrado_clave_local: SecretStr = SecretStr(CLAVE_LOCAL_DESARROLLO)
    cifrado_version_actual: str = "v1"
    cifrado_claves_anteriores: dict[str, SecretStr] = Field(default_factory=dict)
    cifrado_dek_envuelta: SecretStr | None = None
    kms_key_id: str = ""
    kms_region: str = "us-east-1"
    indice_ciego_clave: SecretStr = SecretStr(CLAVE_INDICE_CIEGO_DESARROLLO)

    # Almacén de archivos
    almacen_proveedor: Literal["local", "s3"] = "local"
    almacen_ruta_local: str = "./almacen_local"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"

    # Archivos del estudiante
    archivo_max_bytes: int = 5_242_880
    archivo_mimes_permitidos: list[str] = Field(
        default_factory=lambda: [
            "text/plain",
            "application/pdf",
            "image/png",
            "image/jpeg",
            "image/webp",
        ]
    )
    archivo_retencion_dias: int = 180
    archivo_subido_horas: int = 24
    archivo_max_por_actividad: int = 1
    archivo_texto_max_caracteres: int = 20_000
    archivo_imagen_lado_max: int = 2000

    # Claude
    llm_provider: Literal["fake", "anthropic"] = "fake"
    llm_api_key: SecretStr | None = None
    llm_model_sencillo: str = ""
    llm_model_complejo: str = ""
    llm_timeout_segundos: float = 45
    llm_reintentos_red: int = 2
    llm_max_tokens_cuestionario: int = 6000
    llm_max_tokens_plan: int = 8000
    llm_max_tokens_tutor: int = 8000
    llm_max_tokens_consolidacion: int = 4000
    complejidad_umbral: int = 3
    selector_palabras_largo: int = 60

    # OpenAI
    openai_api_key: SecretStr | None = None
    moderacion_proveedor: Literal["fake", "openai"] = "fake"
    moderacion_modelo: str = ""
    moderacion_umbrales: dict[str, float] = Field(
        default_factory=lambda: {
            "self-harm": 0.3,
            "sexual": 0.5,
            "sexual/minors": 0.1,
            "violence": 0.6,
            "violence/graphic": 0.4,
            "harassment": 0.6,
            "hate": 0.5,
            "illicit": 0.5,
        }
    )
    imagenes_ia_activa: bool = False
    imagenes_ia_proveedor: Literal["fake", "openai"] = "fake"
    imagenes_ia_modelo: str = ""
    imagenes_ia_tamano: str = "1024x1024"
    imagenes_ia_formato: Literal["webp", "jpeg", "png"] = "webp"
    imagenes_ia_max_intentos: int = 1
    imagenes_ia_costo_estimado_usd: float = 0.02
    presupuesto_imagenes_mensual_usd: float = 5.0
    tarifas_ia: dict[str, TarifaModelo] = Field(default_factory=dict)

    # Fuentes de texto
    fuentes_obligatorias: bool = True
    fuentes_max_por_turno: int = 5
    fuentes_cache_dias: int = 30
    fuentes_dominios_permitidos: list[str] = Field(default_factory=list)
    fuentes_proveedores: list[ConfigProveedor] = Field(default_factory=_proveedores_fuentes_falsos)
    fuentes_timeout_segundos: float = 8
    fuentes_idiomas: list[str] = Field(default_factory=lambda: ["es", "en"])
    fuentes_user_agent: str = "TutorIA/0.1 (contacto: definir-en-env)"
    fuentes_extracto_max_caracteres: int = 1500
    fuentes_extracto_herramienta: int = 600
    autoridad_minima_basico: int = 2
    autoridad_minima_intermedio: int = 3
    autoridad_minima_avanzado: int = 3
    fuentes_web_search_activa: bool = False
    fuentes_dominios_web_permitidos: list[str] = Field(default_factory=list)

    # Imágenes abiertas
    imagenes_proveedores: list[ConfigProveedor] = Field(
        default_factory=_proveedores_imagenes_falsos
    )
    imagenes_user_agent: str = "TutorIA/0.1 (contacto: definir-en-env)"
    imagenes_licencias_permitidas: list[str] = Field(
        default_factory=lambda: ["PD", "CC0", "CC-BY", "CC-BY-SA"]
    )
    imagenes_timeout_segundos: float = 10
    imagenes_max_bytes: int = 8_000_000
    imagenes_lado_maximo: int = 1200
    imagenes_ancho_minimo: int = 400
    imagenes_max_redirecciones: int = 3
    imagenes_moderar_externas: bool = True
    imagenes_cache_dias: int = 90
    trabajo_visual_timeout_segundos: int = 120

    # Videos
    videos_proveedor: Literal["fake", "youtube"] = "fake"
    videos_busqueda_dinamica: bool = False
    youtube_api_key: SecretStr | None = None
    videos_canales_confiables: list[str] = Field(default_factory=list)
    video_duracion_min_segundos: int = 240
    video_duracion_max_segundos: int = 1200
    video_metadatos_max_dias: int = 30
    videos_max_resultados: int = 3

    # Diagnóstico y plan
    diagnostico_preguntas: int = 5
    diagnostico_preguntas_min: int = 3
    diagnostico_preguntas_max: int = 5
    umbral_basico: float = 0.4
    umbral_intermedio: float = 0.75
    plan_max_reintentos: int = 2

    # Chat
    chat_ventana_mensajes: int = 30
    chat_max_iteraciones_herramientas: int = 4
    chat_max_busquedas_fuentes: int = 2
    chat_max_reintentos: int = 1
    chat_timeout_turno_segundos: float = 100
    chat_inactividad_minutos: int = 30
    consolidacion_max_caracteres: int = 12_000
    perfil_alpha: float = 0.2
    perfil_observaciones_confianza: int = 10
    perfil_exploracion_cada: int = 4
    tutor_nombre: str = "Vex"

    # Planes y límites
    limite_mensajes_gratis: int = 20
    limite_mensajes_premium: int = 200
    limite_planes_gratis: int = 5
    limite_planes_premium: int = 50
    limite_imagenes_ia_gratis: int = 2
    limite_imagenes_ia_premium: int = 10
    limite_busquedas_video_gratis: int = 5
    limite_busquedas_video_premium: int = 30
    limite_archivos_gratis: int = 3
    limite_archivos_premium: int = 20
    limite_temas_gratis: int = 1
    historial_items_gratis: int = 5
    premium_precio_anual_cop: int = 130_000
    pasarela_proveedor: Literal["fake"] = "fake"
    pasarela_secreto_webhook: SecretStr = SecretStr("solo-desarrollo-secreto-webhook-000000")

    # Seguridad infantil y retención
    lineas_ayuda: list[LineaAyuda] = Field(
        default_factory=lambda: [
            LineaAyuda(nombre="Línea 141 del ICBF", numero="141"),
            LineaAyuda(nombre="Línea de emergencias", numero="123"),
        ]
    )
    retencion_alertas_dias: int = 365
    retencion_mensajes_dias: int = 365
    retencion_consumo_dias: int = 730

    # Protección de datos (Ley 1581)
    responsable_razon_social: str = ""
    responsable_nit: str = ""
    responsable_domicilio: str = ""
    responsable_correo_datos: str = ""
    politica_version: str = "1"
    politica_version_minima_aceptada: str = "1"
    privacidad_plazo_consulta_dias_habiles: int = 10
    privacidad_plazo_reclamo_dias_habiles: int = 15
    festivos_co: list[date] = Field(default_factory=list)

    @property
    def es_produccion(self) -> bool:
        return self.app_env == "production"

    @property
    def es_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @model_validator(mode="after")
    def _validar_configuracion(self) -> Self:
        _validar_llm(self)
        if self.es_produccion:
            _validar_produccion(self)
        return self


def _validar_llm(settings: Settings) -> None:
    if settings.llm_provider != "anthropic":
        return
    faltantes = [
        nombre
        for nombre, valor in (
            ("LLM_API_KEY", settings.llm_api_key and settings.llm_api_key.get_secret_value()),
            ("LLM_MODEL_SENCILLO", settings.llm_model_sencillo),
            ("LLM_MODEL_COMPLEJO", settings.llm_model_complejo),
        )
        if not valor
    ]
    if faltantes:
        raise ValueError(f"LLM_PROVIDER=anthropic requiere: {', '.join(faltantes)}")


def _validar_produccion(settings: Settings) -> None:
    errores = [
        *_errores_secretos(settings),
        *_errores_proveedores(settings),
        *_errores_responsable(settings),
    ]
    if any(PATRON_URL_CON_COMODIN.search(origen) for origen in settings.cors_origins):
        errores.append("CORS_ORIGINS no admite comodines en producción")
    if errores:
        raise ValueError("Configuración de producción inválida: " + "; ".join(errores))


def _errores_secretos(settings: Settings) -> list[str]:
    secretos = {
        "JWT_SECRET": (settings.jwt_secret, SECRETO_JWT_DESARROLLO),
        "INDICE_CIEGO_CLAVE": (settings.indice_ciego_clave, CLAVE_INDICE_CIEGO_DESARROLLO),
    }
    return [
        f"{nombre} debe tener al menos {LONGITUD_MINIMA_SECRETO} caracteres y no ser el de ejemplo"
        for nombre, (valor, ejemplo) in secretos.items()
        if len(valor.get_secret_value()) < LONGITUD_MINIMA_SECRETO
        or valor.get_secret_value() == ejemplo
    ]


def _errores_proveedores(settings: Settings) -> list[str]:
    proveedores = {
        "LLM_PROVIDER": settings.llm_provider,
        "MODERACION_PROVEEDOR": settings.moderacion_proveedor,
        "CORREO_PROVEEDOR": settings.correo_proveedor,
        "CIFRADO_PROVEEDOR": settings.cifrado_proveedor,
        "ALMACEN_PROVEEDOR": settings.almacen_proveedor,
        "PASARELA_PROVEEDOR": settings.pasarela_proveedor,
        "VIDEOS_PROVEEDOR": settings.videos_proveedor,
    }
    errores = [
        f"{nombre}={valor} no se permite en producción"
        for nombre, valor in proveedores.items()
        if valor in PROVEEDORES_FALSOS
    ]
    adaptadores = [*settings.fuentes_proveedores, *settings.imagenes_proveedores]
    if any(p.activo and p.adaptador in PROVEEDORES_FALSOS for p in adaptadores):
        errores.append("los proveedores de fuentes e imágenes 'fake' no se permiten en producción")
    return errores


def _errores_responsable(settings: Settings) -> list[str]:
    campos = {
        "RESPONSABLE_RAZON_SOCIAL": settings.responsable_razon_social,
        "RESPONSABLE_NIT": settings.responsable_nit,
        "RESPONSABLE_DOMICILIO": settings.responsable_domicilio,
        "RESPONSABLE_CORREO_DATOS": settings.responsable_correo_datos,
    }
    return [f"falta {nombre}" for nombre, valor in campos.items() if not valor.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
