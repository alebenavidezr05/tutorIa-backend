# Autorización del acudiente

Un estudiante de 13 a 17 años (edad calculada **en el servidor** a partir de `fecha_nacimiento`)
escribe al registrarse el correo de su madre, padre o representante legal. El backend crea la
cuenta en `PENDIENTE_AUTORIZACION` y le envía al adulto un enlace. El adulto ve un resumen corto y
pulsa **Autorizo** o **No autorizo**. El adulto no tiene cuenta: se identifica con un token de un
solo propósito (`secrets.token_urlsafe(32)`, guardado solo como SHA-256) que viaja en el fragmento
del enlace: `${FRONTEND_URL}/autorizacion/confirmar#token=<token>`.

Ya no existe una ruta pública que envíe correos a direcciones arbitrarias: `POST /autorizaciones`
(solicitud iniciada por el adulto) **se retiró**.

## Endpoints (`/api/v1`)

| Método y ruta | Acceso | Cuerpo → respuesta |
|---|---|---|
| `POST /auth/registro` | público | se añade `correo_acudiente?`: obligatorio de 13 a 17 años, ignorado si es mayor de edad → `201 UsuarioPublico` + cookie |
| `GET /autorizaciones/mia` | sesión (cuenta pendiente permitida) | → `{estado, correo_acudiente_enmascarado, puede_reenviar_en_segundos}` |
| `POST /autorizaciones/reenviar` | sesión (cuenta `PENDIENTE_AUTORIZACION`) | `{correo_acudiente?}` → `202 {mensaje}`; sin correo reenvía al mismo, con correo lo cambia |
| `POST /autorizaciones/consultar` | público, con token | `{token}` → `AutorizacionPublica` |
| `POST /autorizaciones/confirmar` | público, con token | `{token, version_politica}` → `AutorizacionPublica` (`AUTORIZADA`) |
| `POST /autorizaciones/rechazar` | público, con token | `{token}` → `AutorizacionPublica` (`RECHAZADA`) |
| `POST /autorizaciones/revocar` | público, con token | `{token, eliminar_datos}` → `AutorizacionPublica` (sin cambios) |

`AutorizacionPublica`: `estado`, `nombre_estudiante` (solo el primer nombre),
`correo_estudiante_enmascarado` (`d***@gmail.com`), `texto_consentimiento`, `version_politica`,
`permite_compras` (siempre `false`) y `fecha_expiracion_token`.

Estados de `/autorizaciones/mia`: `SIN_SOLICITUD`, `PENDIENTE`, `AUTORIZADA`, `RECHAZADA`,
`REVOCADA`, `EXPIRADA`. Internamente la solicitud usa `PENDIENTE_VERIFICACION` y `VENCIDA`.

## Errores

| Código | HTTP | Cuándo |
|---|---|---|
| `CORREO_ACUDIENTE_REQUERIDO` | 422 | menor sin `correo_acudiente`, o reenvío sin correo y sin solicitud previa |
| `CORREO_ACUDIENTE_INVALIDO` | 422 | correo mal formado o igual al del estudiante (tras normalizar) |
| `EDAD_NO_PERMITIDA` | 422 | menor de 13 años |
| `AUTORIZACION_INVALIDA` | 404 | token inexistente, vencido o reemplazado (mismo error en todos los casos) |
| `POLITICA_DESACTUALIZADA` | 409 | `version_politica` distinta de la vigente: el cliente recarga el texto |
| `DEMASIADAS_SOLICITUDES` | 429 + `Retry-After` | espera mínima, tope por hora o bloqueo por rechazo |
| `OPERACION_NO_PERMITIDA` | 403 | reenviar con una cuenta que no está pendiente |

## Reglas

- **Registro.** La cuenta y la solicitud se crean en la misma transacción. El correo del acudiente
  se guarda cifrado, con su huella HMAC de búsqueda. El correo se envía después del commit; si
  falla, el registro no falla y el estudiante puede reenviar. La respuesta no revela si el correo
  se envió. Si ese acudiente ya superó el tope por hora, se crea la solicitud pero no se envía el
  correo.
- **Confirmar.** En una sola transacción: la solicitud pasa a `AUTORIZADA`, se insertan dos filas
  de `consentimiento` (`TRATAMIENTO` y `TRANSFERENCIA_INTERNACIONAL`) con
  `otorgado_por = REPRESENTANTE_LEGAL`, la versión, el SHA-256 de `texto_consentimiento` y el HMAC
  de la IP del adulto, y la cuenta pasa a `ACTIVA`. Es idempotente. Después se envía al acudiente
  el enlace para revocar.
- **Rechazar.** La solicitud pasa a `RECHAZADA` y la cuenta sigue pendiente. Es idempotente. No
  se envían más correos a ese acudiente por ese estudiante durante
  `AUTORIZACION_BLOQUEO_RECHAZO_DIAS`; el estudiante puede escribir otro correo.
- **Reenviar.** Vence la solicitud pendiente anterior (su token deja de servir) y crea otra con un
  token nuevo. Aplica `AUTORIZACION_REENVIO_ESPERA_SEGUNDOS`, el tope
  `AUTORIZACION_MAX_SOLICITUDES_POR_HORA` (por estudiante y por correo de acudiente) y el bloqueo
  por rechazo.
- **Compras.** La autorización ya no pregunta por compras: `permite_compras` queda en `false` y un
  menor no puede iniciar un checkout (`COMPRA_NO_PERMITIDA`). Es una limitación conocida.
- **Limpieza.** `python -m app.scripts.limpiar_datos_vencidos` suprime las cuentas en
  `PENDIENTE_AUTORIZACION` sin movimiento (registro, solicitud, respuesta o revocación) durante
  `RETENCION_PENDIENTE_DIAS`. Borra también sus solicitudes, con el correo del acudiente, y
  conserva la prueba de consentimiento. **Pendiente de revisión del abogado.**
- **Privacidad.** Los logs no incluyen correos, nombres ni tokens.

## Texto que confirma el adulto

Está en `app/legal/consentimientos_v{POLITICA_VERSION}.json`, clave `autorizacion_acudiente`, y
va versionado con la política. **Pendiente de revisión del abogado.** Si cambia, sube
`POLITICA_VERSION`: la huella registrada es la de la frase exacta que vio el adulto.

## Variables

| Variable | Por defecto | Uso |
|---|---|---|
| `AUTORIZACION_TOKEN_HORAS` | 72 | vigencia del enlace |
| `AUTORIZACION_EXPIRA_DIAS` | 365 | vigencia de una autorización confirmada |
| `AUTORIZACION_MAX_SOLICITUDES_POR_HORA` | 3 | tope por estudiante y por correo de acudiente |
| `AUTORIZACION_REENVIO_ESPERA_SEGUNDOS` | 120 | espera mínima entre reenvíos (nueva) |
| `AUTORIZACION_BLOQUEO_RECHAZO_DIAS` | 7 | bloqueo del mismo correo tras un rechazo (nueva) |
| `RETENCION_PENDIENTE_DIAS` | 30 | supresión de cuentas que nadie autoriza (nueva) |

No requiere migración: `RECHAZADA` cabe en la columna de estado existente (enum no nativo) y la
fecha del rechazo se guarda en `fecha_verificacion`, que es la fecha en que el adulto respondió.
