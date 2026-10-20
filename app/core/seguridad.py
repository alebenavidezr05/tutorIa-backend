"""Lista cerrada de rutas públicas (deny-by-default, §6.6). Cualquier otra exige sesión."""

PREFIJO_API = "/api/v1"

RUTAS_PUBLICAS: frozenset[tuple[str, str]] = frozenset(
    {
        # Crear cuenta: aún no existe sesión.
        ("POST", f"{PREFIJO_API}/auth/registro"),
        # Iniciar sesión: no se puede exigir una sesión para obtenerla.
        ("POST", f"{PREFIJO_API}/auth/login"),
        # Sondas de Docker y del balanceador: no exponen datos.
        ("GET", f"{PREFIJO_API}/health"),
        ("GET", f"{PREFIJO_API}/health/ready"),
        # Deber legal de informar antes de recolectar datos (Ley 1581).
        ("GET", f"{PREFIJO_API}/politica-tratamiento"),
        ("GET", f"{PREFIJO_API}/cumplimiento"),
        # El acudiente no tiene cuenta: se autentica con un token de un solo propósito por correo.
        ("POST", f"{PREFIJO_API}/autorizaciones"),
        ("POST", f"{PREFIJO_API}/autorizaciones/consultar"),
        ("POST", f"{PREFIJO_API}/autorizaciones/confirmar"),
        ("POST", f"{PREFIJO_API}/autorizaciones/revocar"),
        # La pasarela no tiene cookie: se autentica con la firma del cuerpo.
        ("POST", f"{PREFIJO_API}/pagos/webhook/{{proveedor}}"),
    }
)

PREFIJO_WEBHOOK = f"{PREFIJO_API}/pagos/webhook/"
METODOS_MUTACION = frozenset({"POST", "PUT", "PATCH", "DELETE"})
