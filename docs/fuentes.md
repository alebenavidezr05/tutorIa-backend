# Proveedores de fuentes e imágenes abiertas

El código no fija páginas: fija **categorías** (§12.2–§12.3) y cada proveedor se declara en
`FUENTES_PROVEEDORES` / `IMAGENES_PROVEEDORES` (JSON). Agregar un proveedor = un adaptador por
protocolo + una línea en `fuentes/registro.py` o `imagenes/registro.py` + su entrada en `.env`.

Principio: todo dato que el tutor afirme sale de una fuente con **responsabilidad editorial o
institucional identificable**. Revisión de proveedores hecha el **2026-10-29** con peticiones
reales de solo lectura (la anterior fue el 2026-10-18/19). Los términos legales de cada proveedor
deben volver a revisarse antes del lanzamiento comercial.

## Escala de autoridad (2–4)

No existe la autoridad 1: el piso es `AUTORIDAD_PISO = 2` y toda candidata por debajo se descarta.

| Categoría | Dónde se busca | Autoridad |
|---|---|---|
| `ACADEMICA_ABIERTA` | Índices de artículos de acceso abierto, revistas académicas abiertas (incluidas las de América Latina), repositorios institucionales, preprints (marcados «sin revisión por pares») | 4 revisada por pares · 3 repositorio institucional/tesis · 2 preprint |
| `INSTITUCIONAL_OFICIAL` | Ministerios, entidades estadísticas, agencias científicas y de salud, organismos internacionales, legislación, bibliotecas, archivos y museos | 4 |
| `EDUCATIVA_ABIERTA` | Libros de texto y recursos educativos abiertos con revisión editorial o institucional, material curricular oficial | 3 |
| `REFERENCIA` | Enciclopedias y obras de referencia editoriales (con autoría y revisión), diccionarios de academias | 3 |
| `PRENSA_CONFIABLE` | Medios con responsable editorial identificable (ver abajo) | 2 |
| `CURADA` | Fuentes revisadas y cargadas por una persona del equipo | la asignada (2–4) |
| `WEB_GENERAL` | Desactivada por defecto; solo dominios permitidos y nunca los bloqueados | ≤ 2 |

## Fuentes de texto

| Proveedor | Categoría | Adaptador | Estado | Autoridad | Términos y licencia revisados |
|---|---|---|---|---|---|
| OpenAlex (`api.openalex.org/works`) | `ACADEMICA_ABIERTA` | `openalex` | **activo** | 4 si la revista está en DOAJ, 3 tesis o sin dato de revisión, 2 preprint | Metadatos CC0. Sin llave hay un presupuesto diario compartido por IP; con llave gratuita (`api_key`) es mayor: **se recomienda crearla**. El resumen puede tener su propia licencia: solo se usan extractos cortos y siempre se cita la obra. (2026-10-18) |
| MedlinePlus en español (`wsearch.nlm.nih.gov/ws/query`, base `healthTopicsSpanish`) | `INSTITUCIONAL_OFICIAL` | `medlineplus` (XML) | **activo** | 4 | Servicio gratuito, sin registro. Los resúmenes de temas de salud (inglés y español) son de **dominio público** (obra del gobierno de EE. UU.); atribuir «Fuente: MedlinePlus, Biblioteca Nacional de Medicina». Límite: 85 peticiones/min por IP; NLM recomienda caché de 12–24 h (la caché de fuentes es de 30 días). Cobertura: solo salud. El contenido A.D.A.M. y las monografías de medicamentos tienen derechos y no se usan. (2026-10-29) |
| DOAJ (`doaj.org/api/search/articles`) | `ACADEMICA_ABIERTA` | — | **pendiente** (sin adaptador) | 4 | Verificado: API JSON pública, metadatos de artículos y revistas **CC0**, resúmenes en español. Falta implementar el adaptador y confirmar los límites de uso en la documentación de la API. (2026-10-29) |
| Portal CKAN de datos de gobierno | `INSTITUCIONAL_OFICIAL` | `ckan` | **pendiente de verificar** (desactivado) | 4 | `datos.gov.co` usa Socrata (no CKAN) y `datos.gob.ar` respondió 502 en la revisión anterior. |
| Europe PMC, CORE, arXiv, SciELO/Redalyc | `ACADEMICA_ABIERTA` | — | **pendiente de verificar** | 2–4 | No verificados en esta revisión. CORE exige llave; arXiv son preprints (autoridad 2) casi solo en inglés; para SciELO y Redalyc no se confirmó una API pública de búsqueda documentada. |
| Libros de texto abiertos y portales curriculares de ministerios | `EDUCATIVA_ABIERTA` | — | **pendiente de verificar** | 3 | No se encontró una API pública documentada con términos verificables; mientras tanto, la vía es `CURADA`. |
| Enciclopedias editoriales | `REFERENCIA` | — | **vacía y desactivada** | 3 | Ningún proveedor verificado. No se rellena con nada colaborativo. |
| Repositorios institucionales (OAI-PMH) | `ACADEMICA_ABIERTA` | — | **no implementado** | 3 | OAI-PMH no tiene búsqueda por texto: exige cosechar e indexar localmente. |
| Búsqueda web restringida | `WEB_GENERAL` | — | **no implementado** | ≤ 2 | Desactivada (`FUENTES_WEB_SEARCH_ACTIVA=false`). |

Cuando las categorías escolares no alcanzan la autoridad mínima del nivel, el `FuentesService`
suma fuentes académicas. **La vía para elevar la calidad en colegio son las fuentes curadas**:
`python -m app.scripts.cargar_fuentes_curadas data/fuentes_curadas.ejemplo.json` (el ejemplo trae
entradas marcadas «EJEMPLO» que deben completarse con extractos reales antes de cargarlas).

### Prensa confiable (`PRENSA_CONFIABLE`)

- Medio con responsable editorial identificable, notas firmadas, política pública de correcciones
  y separación entre noticia y opinión. Se excluyen columnas de opinión, blogs de los medios,
  contenido patrocinado y agregadores sin criterio editorial.
- Sirve para actualidad y hechos sociales, políticos, culturales o deportivos, y como contexto.
  No respalda sola un hecho científico, técnico o histórico: con `PRENSA_RESPALDA_SOLA=false`
  (por defecto) no cuenta para la autoridad mínima del nivel.
- Solo se guardan título, medio, autor, fecha, URL y el extracto breve que permitan los términos;
  nada de notas completas ni scraping, y se respeta el muro de pago. La vía principal es `CURADA`;
  no hay proveedor automático activo.

## Fuentes excluidas por diseño

Criterio: **no se acepta como fuente nada que cualquier persona pueda editar o publicar sin
revisión** (wikis, foros, blogs, redes sociales, sitios de preguntas y respuestas, apuntes subidos
por usuarios y espejos o derivados de enciclopedias colaborativas). Esto reemplaza la antigua
categoría «colaborativa de autoridad 1».

Lista base (constante en `app/fuentes/bloqueo.py`; incluye todos los subdominios;
`FUENTES_DOMINIOS_BLOQUEADOS` solo puede ampliarla):

- Wikimedia (texto): wikipedia.org, wikibooks.org, wikiversity.org, wikiquote.org, wikinews.org,
  wiktionary.org, wikisource.org, wikivoyage.org, wikidata.org, mediawiki.org, wikimedia.org,
  wikimediafoundation.org.
- Wikis y enciclopedias abiertas o derivadas: fandom.com, wikia.com, wikihow.com, ecured.cu,
  dbpedia.org, wikiwand.com, everipedia.org.
- Contenido de usuarios y apuntes: quora.com, brainly.lat, brainly.com, answers.yahoo.com,
  reddit.com, medium.com, blogspot.com, wordpress.com, tumblr.com, monografias.com,
  rincondelvago.com, buenastareas.com, studocu.com, coursehero.com, scribd.com, slideshare.net,
  academia.edu, facebook.com, x.com, twitter.com, instagram.com, tiktok.com y youtube.com como
  fuente de texto (los videos incrustables siguen su propio flujo).

Se hace cumplir en profundidad: la app no arranca con un proveedor de texto hacia un dominio
bloqueado; el `FuentesService` descarta esas candidatas (y las de autoridad < 2) antes de
deduplicar o guardar; las filas antiguas se filtran al leer; las fuentes curadas se rechazan; una
cita a una fuente bloqueada invalida la respuesta y nunca aparece en las referencias; el validador
de salida rechaza URLs bloqueadas y atribuciones del tipo «según Wikipedia». Para depurar datos ya
guardados: `python -m app.scripts.depurar_fuentes_bloqueadas` (informe) y `--aplicar`.

## Imágenes

| Proveedor | Categoría | Adaptador | Estado | Licencias | Notas |
|---|---|---|---|---|---|
| Wikimedia Commons | `REPOSITORIO_COLABORATIVO` | `mediawiki_commons` | **activo — solo imágenes; sus textos no son fuente** | Por archivo en `extmetadata` (PD, CC0, CC BY, CC BY-SA) | Descripciones, títulos y categorías sirven solo para elegir y atribuir la imagen: nunca se guardan como fuente, no se pasan al modelo como contexto factual y no se citan. Las miniaturas se sirven desde `upload.wikimedia.org` y `thumb.wikimedia.org`: ambos deben estar en `dominios`. |
| Art Institute of Chicago (API + IIIF) | `PATRIMONIO_ABIERTO` | `iiif_museo` | **desactivado** | Solo obras `is_public_domain` (CC0 en datos) | El servidor IIIF devolvió **403** a las descargas del backend en la revisión anterior. |
| NASA Image and Video Library | `CIENCIA_Y_GOBIERNO` | — | **no activado** | — | La API no informa una licencia legible por máquina por imagen. |

Excluidos por diseño (imágenes): buscadores que rastrean la web sin licencia verificable, redes
sociales, bancos con licencias propias y cualquier imagen cuya licencia no se pueda normalizar
(NC y ND siempre se rechazan).
