# Verificación del correo

Toda persona que se registra, menor o mayor de edad, debe confirmar que el correo es suyo antes
de usar la aplicación. Así nadie puede registrarse con la dirección de otra persona.

## Secuencia del registro

```
Persona            Frontend                 Backend                         Correo
  |  formulario  ->  POST /auth/registro  ->  crea usuario (correo_verificado=false)
  |                                           + token de verificación (solo SHA-256)
  |                                           [+ solicitud al acudiente si 13-17 años]
  |                                           commit
  |                <- 201 UsuarioPublico + cookie
  |                                           envía «Confirma tu correo en TutorIA» -> persona
  |                                           [envía enlace de autorización]        -> acudiente
  |  abre ${FRONTEND_URL}/verificar-correo#token=...  (cualquier dispositivo)
  |                ->  POST /auth/verificar-correo {token}
  |                                           correo_verificado=true, token usado
  |                <- 200 {estado: "VERIFICADO"}   (no inicia sesión ni crea cookies)
```

El acceso a la aplicación (dependencia «Activa») exige el **correo verificado** y, si es menor,
además la **autorización del acudiente**. Son dos condiciones independientes: ninguna sustituye a
la otra. Primero se revisa el correo (`CORREO_NO_VERIFICADO`) y luego la autorización
(`AUTORIZACION_PENDIENTE`).

Si el envío del correo falla, el registro no falla: se registra el error sin datos personales y
la persona usa «Reenviar». La respuesta del registro no cambia.

## Endpoints (`/api/v1`)

| Método y ruta | Acceso | Cuerpo → respuesta |
|---|---|---|
| `POST /auth/verificar-correo` | público, con token | `{token}` → `200 {estado: "VERIFICADO"}`; idempotente |
| `POST /auth/verificar-correo/reenviar` | sesión | sin cuerpo → `202 {mensaje}` |
| `GET /auth/verificar-correo/estado` | sesión | → `{correo_verificado, correo_enmascarado, puede_reenviar_en_segundos}` |
| `UsuarioPublico` (`/auth/me`, registro, login) | — | se añade `correo_verificado: bool` |

Permitido sin verificar el correo: `/auth/me`, `/auth/logout`, `/auth/verificar-correo/*`, el
login, `/politica-tratamiento` y `/autorizaciones/mia`. Todo lo demás (diagnóstico, plan,
archivos, tutor, suscripción...) responde `403 CORREO_NO_VERIFICADO`.

## Errores

| Código | HTTP | Cuándo |
|---|---|---|
| `VERIFICACION_INVALIDA` | 404 | token inexistente, vencido o reemplazado por un reenvío (mismo mensaje) |
| `CORREO_YA_VERIFICADO` | 409 | reenviar con el correo ya confirmado |
| `DEMASIADAS_SOLICITUDES` | 429 + `Retry-After` | espera mínima o tope por hora |
| `CORREO_NO_VERIFICADO` | 403 | rutas «Activa» con el correo sin confirmar |

## Reglas

- **Token:** `secrets.token_urlsafe(32)`, guardado solo como SHA-256 en `verificacion_correo`,
  junto con el HMAC del correo para aplicar el tope por dirección. Vence a las
  `VERIFICACION_CORREO_VIGENCIA_HORAS` horas. Un enlace ya usado responde el mismo 200 mientras
  la cuenta esté verificada, y nunca verifica otra cuenta.
- **Reenviar:** invalida los tokens anteriores (adelanta su vencimiento) y crea uno nuevo. Aplica
  `VERIFICACION_REENVIO_ESPERA_SEGUNDOS` y `VERIFICACION_MAX_ENVIOS_POR_HORA` (por usuario y por
  dirección). En el registro, si la dirección ya superó el tope, el token se crea pero el correo
  no sale.
- **Limpieza:** `python -m app.scripts.limpiar_datos_vencidos` suprime las cuentas que no
  confirman su correo en `RETENCION_NO_VERIFICADA_DIAS`, con sus tokens y las solicitudes al
  acudiente. Así se liberan correos ocupados por registros ajenos o con errores de tipeo.
  **Pendiente de revisión del abogado**, junto con los demás plazos de retención.
- **Privacidad:** los logs no incluyen correos, nombres ni tokens. Las respuestas solo muestran
  el correo enmascarado (`a***@example.com`).

## Migración

No hay herramienta de migraciones: el arranque ejecuta `create_all` y luego
`app/core/migraciones.py`, ambos bajo el mismo candado de PostgreSQL. `create_all` crea la tabla
`verificacion_correo`. La migración añade a `usuario` las columnas `correo_verificado` y
`fecha_verificacion_correo` solo si faltan. **Las cuentas existentes quedan con
`correo_verificado = true`** (hoy solo hay cuentas de prueba y no se quiere dejar a nadie
bloqueado) y `fecha_verificacion_correo` en nulo. Las cuentas nuevas nacen en `false`. Se aplica
sola al reiniciar el backend con la versión nueva; no hay que ejecutar nada a mano.

## Variables

| Variable | Por defecto |
|---|---|
| `VERIFICACION_CORREO_VIGENCIA_HORAS` | 24 |
| `VERIFICACION_REENVIO_ESPERA_SEGUNDOS` | 120 |
| `VERIFICACION_MAX_ENVIOS_POR_HORA` | 5 |
| `RETENCION_NO_VERIFICADA_DIAS` | 7 |
