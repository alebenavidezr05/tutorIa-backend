# Proveedores de fuentes e imágenes abiertas

El código no fija páginas: fija **categorías** (§12.2–§12.3) y cada proveedor se declara en
`FUENTES_PROVEEDORES` / `IMAGENES_PROVEEDORES` (JSON). Agregar un proveedor = un adaptador por
protocolo + una línea en `fuentes/registro.py` o `imagenes/registro.py` + su entrada en `.env`.

Revisión hecha el **2026-10-18/19** con peticiones reales de solo lectura. Los términos legales de
cada proveedor deben volver a revisarse antes del lanzamiento comercial.

## Fuentes de texto

| Proveedor | Categoría | Adaptador | Estado | Autoridad | Términos y licencia revisados |
|---|---|---|---|---|---|
| OpenAlex (`api.openalex.org/works`) | `ACADEMICA_ABIERTA` | `openalex` (REST/JSON) | **activo** | 4 si la revista está en DOAJ, 3 tesis o artículo sin dato de revisión, 2 preprint | Metadatos CC0 (documentación oficial). Sin llave hay un presupuesto diario compartido por IP; con llave gratuita (`api_key`) es 10 veces mayor y el uso intensivo es de pago: **se recomienda crear la llave** y ponerla en `llave` del proveedor. El resumen de cada obra puede tener su propia licencia (p. ej. CC BY-NC-ND): solo se usan extractos cortos como contexto y siempre se cita la obra. |
| Wikipedia en español (`es.wikipedia.org/w/api.php`) | `REFERENCIA` | `mediawiki` | **activo** | 1 (colaborativa: nunca respalda sola un hecho) | Texto CC BY-SA 4.0; API pública de MediaWiki con `User-Agent` descriptivo y contacto real obligatorio. |
| Wikilibros en español (`es.wikibooks.org/w/api.php`) | `EDUCATIVA_ABIERTA` | `mediawiki` | **activo** | 1 (colaborativa) | Igual que Wikipedia. |
| Portal CKAN de datos de gobierno | `INSTITUCIONAL_OFICIAL` | `ckan` | **pendiente de verificar** (desactivado) | 4 | No se pudo verificar un portal CKAN en español disponible durante la revisión: `datos.gov.co` usa Socrata (no CKAN) y `datos.gob.ar` respondió 502. Elegir el portal, revisar sus términos y activar. |
| Repositorios institucionales (OAI-PMH) | `ACADEMICA_ABIERTA` | — | **no implementado** | 3 | OAI-PMH no tiene búsqueda por texto: exige cosechar e indexar localmente. Queda como mejora. |
| Búsqueda web restringida | `WEB_GENERAL` | — | **no implementado** | ≤ 2 | Desactivada por defecto (`FUENTES_WEB_SEARCH_ACTIVA=false`); no se eligió una API de búsqueda con términos verificados. |

Como hoy las únicas fuentes escolares verificadas son colaborativas (autoridad 1), el
`FuentesService` agrega fuentes académicas cuando las escolares no alcanzan la autoridad mínima
del nivel. **La vía para elevar la calidad en colegio son las fuentes curadas**
(`python -m app.scripts.cargar_fuentes_curadas data/fuentes_curadas.ejemplo.json`) y un
proveedor institucional verificado.

## Imágenes

| Proveedor | Categoría | Adaptador | Estado | Licencias | Notas |
|---|---|---|---|---|---|
| Wikimedia Commons | `REPOSITORIO_COLABORATIVO` | `mediawiki_commons` | **activo** | Por archivo en `extmetadata` (se aceptan PD, CC0, CC BY, CC BY-SA) | Las miniaturas se sirven desde `thumb.wikimedia.org` (además de `upload.wikimedia.org`): ambos dominios deben estar en `dominios`. |
| Art Institute of Chicago (API + IIIF) | `PATRIMONIO_ABIERTO` | `iiif_museo` | **desactivado** | Solo obras `is_public_domain` (CC0 en datos) | La API de búsqueda responde, pero el servidor IIIF devolvió **403** a las descargas del backend durante la revisión. Revisar sus condiciones de acceso antes de activarlo. |
| NASA Image and Video Library | `CIENCIA_Y_GOBIERNO` | — | **no activado** | — | La API no informa una licencia legible por máquina por imagen (algunas son de terceros con derechos), así que no cumple el criterio de licencia verificable. |

Excluidos por diseño: buscadores que rastrean la web sin licencia verificable, redes sociales,
bancos con licencias propias y cualquier imagen cuya licencia no se pueda normalizar (NC y ND
siempre se rechazan).
