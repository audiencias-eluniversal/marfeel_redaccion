# Contexto del proyecto: Marfeel Redacción

> Documento para que cualquier persona o modelo entienda el proyecto sin historial previo.
> Mantenerlo actualizado cuando cambie algo importante (ver sección "Registro de cambios").

## 1. Objetivo

Descargar de forma automatizada y reproducible consultas de **Marfeel** (plataforma de analítica de medios) para analizar el desempeño del contenido de la redacción de El Universal (Colombia).

Se parte de un **análisis general del contenido de la redacción** y se irá ampliando a **análisis por grupos de trabajo** de la redacción, definidos mediante filtros.

## 2. Fuente de datos

- Un **workspace de Marfeel** que contiene varios **Explore** (vistas de consulta de analítica).
- De esos Explore se guardan consultas con **distintos análisis temporales** (por ejemplo: diario, semanal, mensual, rangos de fechas distintos).
- Acceso por **API** (host `api.newsroom.bi`).

### Autenticación

- `POST https://api.newsroom.bi/api/user/signin` con JSON `{"email": ..., "password": ...}` devuelve un token.
- El token se guarda localmente en `token.json` y se reutiliza.
- **Regla:** si una consulta falla por token inválido o vencido (401/403), se descarta el token, se vuelve a autenticar y se reintenta la consulta una vez.
- Las credenciales viven en `credenciales.md` (privado, nunca copiarlas a otros archivos ni al chat).

## 3. Estructura actual

| Archivo | Para qué sirve |
|---|---|
| `credenciales.md` | Correo y contraseña del signin. **Sensible.** |
| `auth.py` | Lee credenciales, hace signin, guarda y renueva el token (`obtener_token(forzar=False)`). |
| `token.json` | Token vigente en caché. **Sensible**, se regenera solo. |
| `descargar.py` | Ejecuta una consulta de `config/` y guarda CSV + JSON crudo. Uso: `python descargar.py config/qNN_nombre.json` |
| `medium_por_url.py` | Toma el top de URL de un `q02` ya descargado y trae el traffic medium de todas esas URL juntas (groupBy url+medium, paginado). Uso: `python medium_por_url.py config/q02_articulos.json` |
| `periodos.py` | Periodos de análisis: `semana` (lunes a domingo) y `mes` (día 1 a una fecha), su carpeta de salida y los valores por defecto (semana anterior a la actual; mes hasta ayer con los mismos días del mes anterior). |
| `correr_periodo.py` | Corre el análisis de un periodo para el general y todos los equipos: `python correr_periodo.py semana [--inicio YYYY-MM-DD]` o `python correr_periodo.py mes [--inicio --fin]`; `--dry-run` muestra el plan sin llamar a la API. Es el que usará la automatización. |
| `reporte_mensual.py` | Genera `salida/mensual/<mes>/reporte_mensual.html` (un solo HTML con datos incrustados, Chart.js por CDN): totales q01, líneas día a día, top 50 de URL de ambos meses lado a lado con hover de fuentes (q03), fuentes (q05) y secciones (q06, solo general), con selector de equipo. No llama a la API: `python reporte_mensual.py [--mes 2026-11_01-16] [--previo 2026-10_01-16]`. Sin imágenes por ahora; el título sale del slug de la URL. |
| `historico_noche.py` | Ejecución única del histórico: W46 + pausa de 5 min + mensual 1-16 nov (vs 1-16 oct). Escribe el resumen, anota en CONTEXTO.md y apaga el equipo (también con errores; Ctrl+C no apaga). |
| `salida/errores.log` | Registro de errores (hora, entidad, paso, HTTP, cuerpo exacto de la respuesta) y avisos de posible límite de Marfeel. |
| `salida/resumen_ejecucion.md` | Resumen de la ejecución de `historico_noche.py`: matriz de pasos por entidad, errores y verificaciones de cuadre. |
| `config/equipos.json` | Equipos de trabajo: nombre, ids de `tagFamily::filters` y sus etiquetas. Añadir un equipo = añadir una entrada. |
| `correr_equipo.py` | Corre el análisis completo (sin q06) de un equipo: `python correr_equipo.py <equipo> [--forzar]`. ~8 min. Si se interrumpe, al relanzar omite los pasos con CSV ya existente. |
| `config/qNN_nombre.json` | Cuerpo exacto del POST de cada consulta (copiado de Marfeel Explore). |
| `salida/YYYY-WNN_MM-DD/general/` | Resultados del análisis general de esa semana: `qNN_nombre.csv` y `qNN_nombre.json`. |
| `salida/YYYY-WNN_MM-DD/equipos/<equipo>/` | Resultados por equipo de trabajo (fase 2, aún no generados). Mismos nombres de archivo, sin q06. |
| `CONTEXTO.md` | Este documento. |

### Consultas hechas

| Archivo | Qué es | groupBy | Comparación |
|---|---|---|---|
| `q01_general` | Totales del dominio por día: pageViewsTotal, uniqueUsers, newArticles, averageDurationPerPage | ninguno | Sí, semana anterior |
| `q02_articulos` | Top 50 URL: pageViewsTotal, averageDurationPerPage, socialPosts | `url` | No (solo el range) |

| `q02_articulos_semana_anterior` | Igual que `q02_articulos` pero para la semana previa (26 oct a 1 nov) | `url` | No |

| `q05_fuentes_trafico` | **Análisis global por fuentes de tráfico** (importante): uniqueUsers, pageViewsTotal, averageDurationPerPage por medium de todo el dominio | `medium` | Sí, semana anterior (columnas `_comparada`) |
| `q06_secciones` | Análisis por secciones: pageViewsTotal, uniqueUsers, averageDurationPerPage por `section`, con filtro `section neq 0` | `section` | Sí, semana anterior (columnas `_comparada`) |
| `q03_medium_articulos` / `q03_medium_articulos_semana_anterior` | Traffic medium de las 50 URL de cada q02, generado por `medium_por_url.py` (no tiene JSON de config propio: se construye desde el CSV del q02) | `url`+`medium` | No |

`q05_fuentes_trafico` (W45, 30 mediums, 1 petición) se ejecuta con `descargar.py` y **ya trae la comparación con la semana anterior en el mismo CSV** (no se descarga aparte para W44). Sus totales cuadran con q01 (1.623.306 vistas, 696.643 usuarios). La suma de mediums no coincide con el total: usuarios únicos suma de más (30.426 en W45; un usuario puede llegar por varios mediums) y vistas difiere en ambos sentidos (-11.921 en W45, +3.098 en la semana comparada), causa no confirmada. Usar siempre la fila `TOTAL_CONSULTA` como total.

`q06_secciones` (W45, top 50 secciones, 1 petición) también trae la comparación en el mismo CSV. **Decisión del usuario: el top 50 es suficiente, no se pagina.** Su `TOTAL_CONSULTA` (1.341.237 vistas) es menor que el del dominio porque el filtro `section neq 0` excluye páginas sin sección (ej. la portada). Los nombres de sección vienen como los define Marfeel (mezcla de mayúsculas/minúsculas, ej. `Atlántico`, `Loterias`).

Ejecutado para W45 (579 filas) y W44 (543 filas), 2 peticiones por semana. `config/q03_medium_url.json` es solo el ejemplo de una URL y `config/q04_prueba_url_medium.json` la prueba de 2 URL.

**Columnas de `q03_medium_*.csv`:** `posicion_url` (puesto en el q02), `url`, `tipo_url`, `seccion`, `medium`, `pageViewsTotal`, `averageDurationPerPage`, `socialPosts`, `pct_vistas_url` (peso del medium sobre el **total real de la URL**, tomado de q02, no sobre la suma de mediums).

**Clasificación `tipo_url`:** `home` (raíz del dominio), `seccion` (cualquier ruta sin fecha, incluye subsecciones), `articulo` (ruta con `/YYYY/MM/DD/`), `tag` (ruta con `/tag/` o `/tags/`, agrupación temática; aún no ha aparecido). `seccion` = ruta antes de la fecha (artículos) o la ruta misma (secciones).

**Total de cada URL:** es el `pageViewsTotal` de la lista de artículos (q02), no una suma de mediums. No se calcula ni se usa ningún "Others": la API devuelve cada medium con su valor y los CSV no agrupan ni reclasifican mediums.

**Relaciones entre mediums (dadas por el usuario; solo informativas, no aplicadas en los datos):** `discover` y `gnews` (Google News) son `search`; `taboola_news` es `referral`; `facebook` es `social`. Por eso un mismo tráfico aparece en más de un medium.

**Regla de análisis sobre mediums:** nunca sumar mediums entre sí ni usar esa suma como total; se solapan (jerarquías como discover⊂search, facebook⊂social). Los porcentajes se calculan contra el total de la URL y no suman 100 %. Si se necesita una vista excluyente hay que definir antes qué mediums son "padre" y cuáles "hijo" (pendiente que lo defina el usuario). `medium_por_url.py ... --sin-api` regenera el CSV desde el `.json` guardado sin gastar peticiones.

**Notas:** `socialPosts` por medium sale 0 (es un dato por URL, no por medium; usar el valor de q02). Las 50 URL se incluyen tal cual (home y secciones incluidas); filtrar por `tipo_url` al analizar. Orden de ejecución para una semana nueva: `descargar.py` del q01 y del q02, luego `medium_por_url.py`; repetir para la semana anterior.

**Regla de trabajo:** cada análisis que no lleve `compare` se descarga **dos veces**: la semana de interés y la semana inmediatamente anterior (mismo body, solo cambia `dates.range`). La versión de la semana anterior se guarda como `qNN_<nombre>_semana_anterior.json` y su resultado cae automáticamente en su propia carpeta de semana (ej. `salida/2026-W44_10-26/general/`). Así se pueden comparar los tops de dos semanas.

Dominio filtrado en todas: `www.eluniversal.com.co`.

## 3.1 API de consultas (base de todos los Explore)

- `POST https://api.newsroom.bi/api/dashboard/query` con cabecera `Authorization: Bearer <token>`.
- El body es la consulta del Explore: `dates.range` (start/end), `compare` (opcional), `filters`, `groupBy`, `metrics`, `order`, `from`/`limit`.
- Respuesta: **una entrada por métrica**. Cada una trae `actualData` (y `compareData` si hubo `compare`) con:
  - `total`: total de la métrica en el rango (para promedios, es un promedio, no suma).
  - `data`: serie por día (`label` + un valor por cada `key`).
  - `values`: un elemento por cada valor del `groupBy`, con `key` (hash) y `total`; `items[].value` es el valor legible (ej. la URL).
  - Los `key` coinciden entre métricas de una misma consulta, así se unen.
- Sin `groupBy`: CSV con una fila por día (`fecha`, `fecha_comparada`, métrica, métrica_comparada) + fila `TOTAL`.
- Con `groupBy`: CSV con una fila por elemento (`posicion`, dimensiones, métricas con el total del rango; si hay `compare`, una columna `<métrica>_comparada` por métrica) + fila `TOTAL_CONSULTA` (total de todo, no solo del top devuelto).

### Periodos y carpetas (actualizado 2026-11-17)

- Semana: `salida/YYYY-WNN_MM-DD/`. Mes: `salida/mensual/YYYY-MM_DD-DD/` (ej. `mensual/2026-11_01-16`). Dentro de cada una: `general/` y `equipos/<equipo>/`.
- Cada carpeta de periodo es autónoma. Los periodos **nuevos** guardan el top 50 y el medium con los nombres estándar (`q02_articulos.csv`, `q03_medium_articulos.csv`), también cuando son el periodo previo de otro (sin sufijo `_semana_anterior`; ese sufijo solo existe en W44, que se descargó antes). Por eso W46 reutiliza el top 50 y el medium de W45 como "semana anterior" sin volver a pedirlos, y cada análisis semanal siguiente reutiliza los de la semana previa.
- Un paso se omite si su CSV ya existe (se puede relanzar sin repetir peticiones; `--forzar` repite).
- `q01`, `q05` y `q06` llevan la comparación en sus propias columnas `_comparada`; solo `q02` y `q03` se piden por separado para el periodo previo.
- Mes previo = mismos días del mes anterior; si ese mes es más corto, se recorta a su último día.

### Errores y límite de Marfeel

`descargar.consultar()` lanza `ErrorAPI(status, cuerpo)` tras agotar 6 intentos (429, 5xx, errores de red) o ante un error no reintentable (400...). `correr_periodo.py` documenta cada fallo en `salida/errores.log`, sigue con los demás pasos y, al terminar la ronda, reintenta los fallidos una vez tras 5 min. Si **3 pasos seguidos agotan los reintentos con 429**, lo trata como un posible límite impuesto por Marfeel: lo anota, espera 15 min y reintenta; tras 3 enfriamientos sin éxito abandona el resto (marcado "no ejecutado"). Los otros errores no activan ese modo.

### Convención de carpetas de semana

Estructura: `salida/<semana>/general/` (análisis general) y `salida/<semana>/equipos/<equipo>/` (un equipo, nombre sin tildes ni espacios, ej. `entretenimiento`). La semana anterior tiene su propia carpeta con la misma estructura (ahí caen los `_semana_anterior`). `descargar.py` expone `carpeta_salida(inicio, subcarpeta="general")` para elegir la subcarpeta.

Nombre de la carpeta de semana: `YYYY-WNN_MM-DD`: año ISO, `W` + número de semana ISO con 2 dígitos (semanas que arrancan lunes), y fecha de inicio del `range`. Ej.: `2026-W45_11-02`. Se calcula desde `dates.range.start`.

### Comportamientos a tener en cuenta

- **Límite de peticiones (documentado por Marfeel):** **1 petición por minuto y 500 filas por respuesta, por cuenta**, compartido por todos los usuarios y procesos de la cuenta. Mensaje al excederlo: `{"msg":"Exceeded rate limit"}` (HTTP 429, sin cabecera `Retry-After`). Probado: 5 s y 30 s entre peticiones fallan. Se usa **65 s** entre peticiones. `descargar.py` reintenta tras 429 con espera fija de 65 s (hasta 6 intentos). Paralelizar no ayuda. Subir el límite solo se pide al account manager de Marfeel.
- **Verificado (2026-11-16):** el filtro `url` con `op: eq` acepta **varias URL** en `value` (se combinan con OR) y `groupBy: ["url","medium"]` devuelve una fila por combinación, sin mezclar URL. Con 2 URL: 27 filas en 1 petición. Los totales por medium de una URL coinciden con la consulta individual (ej. social = 196415). La suma de los mediums **supera** el total de la URL porque **los mediums no son excluyentes**: unos están incluidos en otros (ej. `discover` dentro de `search`, `facebook` dentro de `social`). Prueba guardada en `config/q04_prueba_url_medium.json`. Consecuencia: el análisis por medium de ~50 notas cuesta ~2 peticiones (500 filas por página), no 50.
- **Lógica de filtros (probado 2026-11-17, W45, dominio completo):** entre filtros distintos se combinan con **AND** (`url like loteria` = 48.638 vistas; añadiendo `url like resultado` baja a 47.984). Los **valores dentro de un mismo filtro** se combinan con **OR** (`url like ["loteria","chance"]` = 48.681, más que `loteria` sola y menos que la suma de `loteria` 48.638 + `chance` 38.742). `like` funciona como "contiene" sin comodines. **No se encontró forma de anidar un OR entre filtros distintos**: se probaron `{"op":"or","filters":[...]}`, `{"filter":"or","value":[...]}` y listas de listas, y la API los **ignora en silencio** (devuelve el total sin filtrar, 1.623.306). Ojo: **la API no valida los filtros**; un operador inventado (`op:"or"`) devolvió 200 con 0 vistas y una estructura no reconocida se ignora sin avisar. Tras cualquier consulta con filtros nuevos, comprobar que el total tenga sentido.
- **Paginación:** `limit` máximo 500, `from` es el desplazamiento. Enviar siempre `limit` y `from`. No hay campo de "siguiente página": se corta cuando llega una página con menos filas que `limit`.
- **Token:** válido hasta 14 días desde su generación; se renueva repitiendo el signin. Marfeel recomienda un usuario genérico con rol API para automatizar.
- Fuentes: https://www.marfeel.com/docs/analytics/api-docs/marfeel-reporting-api-developer-guide y https://www.marfeel.com/docs/analytics/api-docs/marfeel-api-authentication-with-bearer-tokens
- **Token inválido (401/403):** se renueva una vez y se reintenta.
- **Los datos por URL mezclan** artículos con portada (`eluniversal.com.co`) y páginas de sección (`/sucesos/`). El top 50 cubre ~60% de las vistas totales; para más hay que paginar con `from`/`limit`.

## 3.2 Fase 2: análisis por equipos de trabajo

**Idea:** el workspace de Marfeel es el mismo para todos los equipos; un equipo se define **solo por un filtro** `tagFamily::filters` (doble `::`). Se repite todo el análisis general **excepto secciones** (q06): q01, q02 (+semana anterior), q03_medium (+semana anterior) y q05.

**Cómo se deduce el filtro desde una URL de Compass/Explore** (formato confirmado con un ejemplo del usuario):
- En la URL, cada valor del filtro `tagFamily::filters` tiene un nombre (`...value[i].name` o `.label`) y un id (`...value[i].id` o `.value`).
- En el body de la API van **solo los ids, como números**, y los nombres se usan como etiquetas.
- El filtro va **además** del de dominio (`domain eq www.eluniversal.com.co` primero, `tagFamily::filters` después). Los ids se combinan con OR.
- Se mantienen rangos de fechas absolutos (no `preset`). Lo demás de la URL (`groupedBy`, `selectedChartType`, `workspaces/NNN`, `schedule...`) es solo de la interfaz y no entra al body.

```json
{"filter":"tagFamily::filters","op":"eq","value":[6954401444,6974778654,6974700784]}
```
Ejemplo de referencia del usuario (equipo no nombrado): etiquetas `02j2s7m0_etp`=6954401444, `27j0y6o0_eps`=6974778654, `41u9a1z1_zbo`=6974700784.

**Equipos recibidos:** `Entretenimiento` (carpeta `entretenimiento`), ids 6961602867, 6961635296, 6961661940, 6999832350, 7201619325 con etiquetas `06o8i4h1_lmb`, `22c1x5q8_acm`, `26n0l8b7_dah`, `47j4g5d2_mcs`, `50n4c5v1_amc`.

**Implementado (2026-11-16):** `descargar.py` y `medium_por_url.py` aceptan `--equipo <slug>` (añaden el filtro `tagFamily::filters` tras el de dominio y escriben en `salida/<semana>/equipos/<slug>/`); `correr_equipo.py` encadena los 6 pasos (q01, q02, q03_medium, q02 semana anterior, q03_medium semana anterior, q05). Las mismas consultas de `config/` sirven para todos los equipos: el filtro se inyecta al ejecutar. `consultar()` espacia solo las peticiones (65 s) y ya no depende de recibir 429.

**Equipos configurados:** `entretenimiento` (5 ids), `locales` (5 ids: 6962504772 `09j6h5g0_wmg`, 6999505460 `48v9t6r1_bfr`, 6993931374 `44u3l19f_epp`, 6961608808 `33y2v2r4_jgo`, 6999456992 `49x3n6i8_saa`; descargado W45 y W44) y `sucesos` (4 ids: 6954401444 `02j2s7m0_etp`, 6961710902 `25o6b1q7_daz`, 6961607591 `34f3w2i6_lab`, 6974700784 `41u9a1z1_zbo`). Sucesos descargado para W45 y W44. El ejemplo de prueba que pasó el usuario compartía 2 ids con Sucesos (`02j2s7m0_etp`, `41u9a1z1_zbo`) y tenía uno más (`27j0y6o0_eps`=6974778654) que no está en Sucesos.

`web` (8 ids de tagFamily: 6974820169, 6962143103, 6974778654, 6961731696, 6993956379, 6993910968, 6959720528, 7290226008) **con filtro extra** `section neq 49937656` (se analiza sin la sección Loterias). Los filtros adicionales de un equipo van en el campo opcional `filtros_extra` de `config/equipos.json` y `aplicar_equipo()` los añade a todas las consultas del equipo. Web descargado para W45 y W44 el 2026-11-17 y **regenerado con la exclusión de URL de loterías** (los archivos anteriores se reemplazaron; q01 W45: 301.891 vistas contra 215.650 de W44). **Matiz (superado por la exclusión de URL, ver abajo):** el filtro `section neq Loterias` por sí solo excluye la *sección de Marfeel* "Loterias" (id 49937656), no los artículos que traten de loterías: en el top 50 de Web hay notas de resultados de loterías (ej. "loteria-de-medellin-resultados...") cuya sección en Marfeel es `colombia` (id 35503659) y por eso se mantienen. Ids de sección vistos: `colombia` 35503659, `sucesos` 35503660.

`monetizacion` (2 ids de tagFamily: 6984803484 `73k6j9w1_cc2`, 6964930484 `43e1b4g6_cap`; sin filtros extra; descargado W45 y W44).

`editor-economia` ("Editor Economía"; 1 id de tagFamily: 6954401445 `04z7w7l8_hfa`; sin filtros extra; descargado W45 y W44).

`mundo` ("Mundo"): equipo definido **solo por sección**, `filtros_extra` = `section eq 35503667` (`mundo`), sin tagFamily. Descargado W45 y W44.

`economia` ("Economía"): equipo definido **solo por sección**, `filtros_extra` = `section eq 35503673` (`economica`), sin tagFamily. Es distinto de `editor-economia` (que se define por tagFamily). Descargado W45 y W44.

`deportes`: equipo definido **solo por sección** (sin `tagFamily`), `filtros_extra` = `section eq 35503658`. La sección `Fútbol` (id 49601111) es aparte y no se incluye. Descargado W45 y W44. `_filtros_equipo` solo añade `tagFamily` si el equipo lo define.

**Exclusión de notas de loterías en Web (regla `exclusion_urls` en `config/equipos.json`):** la API no anida OR entre filtros, así que antes de las consultas se lista, por semana, las URL de la sección `colombia` (id 35503659) del equipo cuya ruta contiene (`loteria` o `chance`) y `resultado`: una consulta con `groupBy url`, filtros `section eq 35503659`, `url like ["loteria","chance"]` (OR entre valores) y `url like ["resultado"]` (AND entre filtros). El resultado se guarda en `salida/<semana>/equipos/web/urls_excluidas.csv` (+ `.json`) y las consultas del equipo añaden `url neq [lista]` (la unión de las listas del periodo y del comparado). Si el equipo define la regla y falta la lista de algún periodo, el código se detiene (no sigue sin excluir). Una lista vacía no se envía. `correr_equipo.py` genera las listas que falten (paso 0). Para una semana nueva, las listas de la semana anterior se reutilizan. La lista no solo incluye las notas de la semana: trae URL antiguas con tráfico residual (W45: 135 URL, 8.720 vistas; W44: 134 URL, 10.770 vistas).

**Estado de equipos:** `entretenimiento` descargado para W45 y W44 (W45: 92.551 vistas y 64.771 usuarios únicos; semana anterior 187.220 vistas; totales de q01 y q02 cuadran). Los top 50 de este equipo son todos artículos (sin home ni secciones). Para añadir un equipo: pasar su URL de Compass, añadirlo a `config/equipos.json` y ejecutar `python correr_equipo.py <slug>`.

**Diseño original:** `config/equipos.json` con nombre y ids de cada equipo; salida en `salida/<semana>/equipos/<equipo>/`; ~8 peticiones por equipo (~9 min con la pausa de 65 s del límite de la API).

## 3.3 Ejecución del histórico (2026-11-17)

Plan acordado con el usuario (para dejar un histórico para una reunión): W46 (9-15 nov, comparada con W45) para el general y los 9 equipos; pausa de 5 min; análisis mensual 1-16 nov comparado con 1-16 oct, también general y los 9 equipos. Sin alertas sonoras; todo se documenta en `salida/errores.log` y `salida/resumen_ejecucion.md`; el equipo se apaga al terminar aunque haya errores (`shutdown /s /t 60`, cancelable con `shutdown /a`). El script impide que Windows suspenda el equipo mientras corre. Esta ejecución es solo para el histórico; después el análisis lo lanzará un script de forma recurrente: semanal = semana anterior a la actual; mensual = del día 1 hasta ayer.

Verificaciones automáticas del resumen: total del q02 igual al del q01 (periodo y previo); Deportes, Economía y Mundo contra su fila del q06 general; Web: tamaño de las listas de exclusión y ninguna URL con "loter" en su top 50. Riesgo conocido: en el mensual de Web, la lista `url neq` será más larga que las 200 URL ya probadas; si la API la rechaza, quedará en errores.log.

## 4. Diseño previsto (para crecer)

Idea central: **separar qué se consulta (configuración) de cómo se descarga (código)**, para añadir análisis sin tocar el código.

```
marfeel_redaccion/
├── auth.py              # autenticación (hecho)
├── descargar.py         # ejecuta consultas definidas en config, guarda CSV (pendiente)
├── config/
│   ├── explores.json    # Explore del workspace: id, endpoint, métricas/dimensiones base
│   ├── periodos.json    # análisis temporales reutilizables (diario, semanal, rangos...)
│   └── grupos.json      # filtros por grupo de trabajo de la redacción (fase 2)
└── salida/
    └── <explore>/<periodo>[__<grupo>].csv   # un CSV por consulta
```

Cada consulta = **Explore + periodo + (opcional) grupo de trabajo**. El script combina esas piezas, así:
- Fase 1 (general): Explore × periodos, sin filtros de grupo.
- Fase 2 (grupos): se añade un `grupo` cuyo filtro se inyecta en la consulta base; el resto del código no cambia.

## 5. Decisiones tomadas

- Un **CSV por consulta** (no un archivo único consolidado).
- Autenticación por API con renovación automática de token.
- Lenguaje: Python con `requests`.
- Configuración externa (JSON) en vez de consultas escritas en el código.
- Todas las consultas "Explore" usan el mismo POST base (`/api/dashboard/query`).
- Los resultados se organizan por semana en `salida/YYYY-WNN_MM-DD/`.

## 6. Pendiente / información que falta

- [x] Petición real de un Explore y estructura de respuesta (hechas q01 y q02).
- [ ] Lista de los demás Explore del workspace y análisis temporales que se quieren de cada uno.
- [ ] Definición de los **filtros por grupo de trabajo** (el usuario los entregará después).
- [x] Análisis por URL y medium: hecho para W45 y W44 con `medium_por_url.py`.
- [ ] Ejecutar varias consultas en lote con pausa fija entre ellas (hoy se corre una por una).
- [ ] Decidir si las URL se filtran a solo artículos (excluir portada/secciones) y si se pagina más allá de 50.
- [ ] Mover periodos y grupos a `config/periodos.json` / `config/grupos.json` cuando haya varias consultas (hoy cada consulta lleva sus fechas dentro del JSON).

## 7. Reglas para quien continúe el proyecto

1. No escribir credenciales ni tokens en código, logs, ni en este documento.
2. No inventar el formato de la API de Marfeel: basarse en peticiones reales proporcionadas por el usuario.
3. Para añadir un análisis nuevo, preferir editar `config/` antes que el código.
4. Antes de ejecutar descargas masivas, probar con una sola consulta.
5. Si el proyecto se sube a git, excluir `credenciales.md` y `token.json`.

## 8. Registro de cambios

- 2026-11-17: Refactor para periodos arbitrarios (semana o mes): `periodos.py`, `correr_periodo.py`, `historico_noche.py`; `descargar.ejecutar()` y `medium_por_url.ejecutar()` reciben la carpeta del periodo; `ErrorAPI`, contadores de peticiones, documentación de errores y detección de posible límite. Probado sin API (CSV de medium regenerados idénticos, cuadres y detección de límite simulada). Copia del código anterior en la carpeta temporal de la sesión.

- 2026-11-17: Descargado Monetización para W45 y W44 (6 pasos, sin errores).
- 2026-11-17: Descargado Editor Economía para W45 y W44 (6 pasos, sin errores).
- 2026-11-17: Añadido el equipo `mundo` (solo `section eq 35503667`, sin tagFamily) y descargado W45 y W44. Con este quedan descargados los 9 equipos recibidos.
- 2026-11-17: Añadido el equipo `economia` (solo `section eq 35503673`, sin tagFamily) y descargado W45 y W44.
- 2026-11-17: Añadido el equipo `editor-economia` a `config/equipos.json` (aún sin descargar).
- 2026-11-17: Añadido el equipo `deportes` (solo `section eq 35503658`, sin tagFamily) y descargado W45 y W44. `aplicar_equipo` admite equipos sin tagFamily.
- 2026-11-17: Añadido el equipo `monetizacion` a `config/equipos.json` (aún sin descargar).
- 2026-11-17: Web regenerado excluyendo las URL de loterías (`url neq` con la lista semanal de `urls_excluidas.csv`). Código: `cargar_exclusiones`, `generar_exclusiones`, `aplicar_equipo` en `descargar.py`; paso 0 en `correr_equipo.py`. Verificado: ninguna URL excluida ni con "loter" queda en q02/q03.
- 2026-11-17: Probada la lógica de filtros de la API (AND entre filtros, OR entre valores de un filtro, sin OR anidado). Sin cambios en datos.
- 2026-11-17: Descargado Web para W45 y W44 (6 pasos, sin errores).
- 2026-11-17: Añadido el equipo `web` (con `filtros_extra` para excluir la sección Loterias) y soporte de `filtros_extra` en `aplicar_equipo()`. Descarga lanzada.
- 2026-11-16: Descargado Locales para W45 y W44 con `correr_equipo.py` (6 pasos, sin errores).
- 2026-11-16: Añadido el equipo `locales` a `config/equipos.json` (aún sin descargar).
- 2026-11-16: Descargado Sucesos para W45 y W44 con `correr_equipo.py` (6 pasos, sin errores).
- 2026-11-16: Añadido el equipo `sucesos` a `config/equipos.json` (aún sin descargar).
- 2026-11-16: Implementada la fase 2 (`--equipo`, `config/equipos.json`, `correr_equipo.py`, espaciado automático de peticiones). Descargado Entretenimiento para W45 y W44 (6 pasos, 8 peticiones, sin errores).
- 2026-11-16: Reorganizadas las carpetas: lo ya descargado de W45 y W44 se movió a `general/` y los scripts escriben ahí. Reservada `equipos/<equipo>/` para la fase 2. No se ha generado nada de Entretenimiento. CSV verificado idéntico tras la migración.
- 2026-11-16: Documentada la fase 2 (equipos): cómo deducir el filtro `tagFamily::filters` desde las URL de Compass. Nada ejecutado aún.
- 2026-11-16: Añadido `q06_secciones` (top 50, con comparación). Ejecutado para W45. Decisión: no paginar, 50 filas bastan.
- 2026-11-16: Añadido `q05_fuentes_trafico` (global por medium, con comparación). `descargar.py` ahora soporta groupBy + compare en el CSV. Ejecutado para W45.
- 2026-11-16: Se probó y se **retiró** la columna `grupo_medium` (principal/otros): el usuario pidió no trabajar con "Others" ni asumir agrupaciones. CSV de W45 y W44 regenerados sin API.
- 2026-11-16: Corregido `pct_vistas_url` (antes `pct_vistas_en_url`, usaba la suma de mediums como denominador, incorrecto porque los mediums se solapan). Ahora usa el total de la URL del q02. CSV de W45 y W44 regenerados sin llamar a la API.
- 2026-11-16: Creado `medium_por_url.py` y ejecutado q03_medium para W45 y W44 (50 URL por semana, home/secciones/artículos clasificados). 4 peticiones en total.
- 2026-11-16: Probado q04 (2 URL con groupBy url+medium): funciona en una sola petición. Resuelto abajo.
- 2026-11-16: Investigado el límite de la API (1 req/min por cuenta, 500 filas). `descargar.py` ahora espera 65 s tras un 429. Creado `config/q03_medium_url.json` (ejemplo de una URL con groupBy medium; aún sin ejecutar en lote).
- 2026-11-16: Añadido `q02_articulos_semana_anterior` (2026-W44_10-26). Establecida la regla de descargar cada análisis también para la semana anterior.
- 2026-11-16: Añadidos `descargar.py`, `q01_general` (con comparación semanal) y `q02_articulos` (groupBy url). Primera semana descargada: 2026-W45_11-02. Documentada la API y el manejo de 429.
- 2026-11-16: Creación del proyecto. Autenticación implementada y probada. Definido el diseño de crecimiento.

## 9. Ejecuciones automáticas

Líneas añadidas por los scripts al terminar una ejecución (la de `historico_noche.py` la añade ella misma).
- 2026-11-17 04:05: histórico W46 + mensual 1-16 nov (vs 1-16 oct). Pasos: {'OK': 105, 'OMITIDO': 21}. Peticiones: 113 (429: 0). Verificaciones con ALERTA: 0. Equipo apagado al terminar. Detalle en salida/resumen_ejecucion.md y salida/errores.log.


## Actualización de equipos según periodistas.txt (2026-11-17)
- Fuente: `periodistas.txt` (Periodista;Código;Grupo). `config/equipos.json` actualizado (copia previa: `config/equipos.json.bak_antes_periodistas`). No se tocó nada de `salida/`: lo descargado sigue con la composición anterior.
- Quitados por ya no trabajar: `22c1x5q8_acm` (Entretenimiento, id 6961635296), `34f3w2i6_lab` (Sucesos, id 6961607591), `49x3n6i8_saa` (Locales, id 6999456992). El emparejamiento código-id se dedujo por posición (arrays paralelos; verificado con los ejemplos etp, eps, zbo).
- Nuevos SIN id de tagFamily aún (campo `pendientes_id`, no afecta a las consultas): `52k8j5v7_spo` Stefanny Padilla Olmos (Sucesos) y `42k5r0v9_jmc` Juan Manuel Cantillo Arrieta (Web). Hasta tener sus ids, esos equipos no cuentan lo de esas personas.
- Deportes, Economía y Mundo siguen por filtro de sección. `editor-economia` (Hermes Figueroa, `04z7w7l8_hfa`) es caso aparte. Los códigos `24f9t7x4_ccv` y `28h9a6j2_ead` (Deportes) no se usan.
- Monetización coincide con el archivo.

- 2026-11-17: Ids recibidos del usuario (por URL de Compass): `52k8j5v7_spo`=7319363934 (añadido a Sucesos), `42k5r0v9_jmc`=6963067561 (añadido a Web), `24f9t7x4_ccv`=6967567259 y `28h9a6j2_ead`=6961603561 (Deportes, no usados: Deportes sigue por sección). `pendientes_id` eliminado. `periodistas.txt` tiene ahora la columna `Value` (id tagFamily; copia `periodistas.txt.bak`).
- 2026-11-17: Nuevo `puntual_equipos_visitas.py`: artículos publicados 1-16 nov por título y grupos de visitas, para sucesos, entretenimiento, locales, web (con exclusión de URL del mes), deportes, economia, mundo y editor-economia. Salida en `salida/puntuales/2026-11-01_2026-11-16_articulos_por_visitas/equipos/<slug>/` y `resumen_equipos.json`. Monetización no incluida (sin confirmar).

- 2026-11-17: Descargados los 8 equipos de `puntual_equipos_visitas.py` (9 peticiones, 0 429). Deck (artefacto RJqtzByDu3Wvg7RRENTXiB, v7) con 2 diapositivas por equipo (grupos y peso en visitas) generadas por `gen_equipos.py` (en el scratchpad de la sesión) desde `resumen_equipos.json`. Los equipos no suman el general (firmas compartidas).

- 2026-11-18: Nuevo `puntual_contenidos_camara.py` (informe Cámara de Comercio de Cartagena): lee `salida/puntuales/2026-11-18_CAMARA_CCIO/contenidos.txt` (39 ítems: 27 artículos de El Universal, 10 reels/posts de Instagram, 2 enlaces de Drive) y saca páginas vistas y usuarios únicos de los 27 artículos desde la fecha de su URL hasta hoy. Salida: `metricas_marfeel.csv`, `resumen.md/.json`, `redes_y_drive.csv`, `consultas/`. 4 peticiones: una agrupada por URL (filtro `url eq` con 27 valores), dos por bloque (usuarios únicos sin duplicar) y una de control. Hallazgo: una consulta SIN agrupar debe llevar `"groupBy": []` explícito y `order` `{metric, sort}`; sin ello la API respondió HTTP 500. El control (una URL con su propia fecha) dio 439 vistas contra 435 en la agrupada, y el bloque CISE 7.588 contra 7.585 de la suma: diferencias de 3 a 4 vistas, compatibles con tráfico del día entre peticiones (no verificado).
- Drive/Instagram sin login (probado 2026-11-18): el PDF de Drive no es legible (solo "Cargando"; título "CCC SANTA ROSA DE LIMA-Página 4-UNICA.pdf"); la carpeta de fotos es visible (50 nombres "Cise zona norte N.jpeg", carpeta "Fotografías CISE ZONA NORTE"); Instagram devuelve solo muro de login, sin métricas.

- 2026-11-18: Informe Cámara de Comercio: el usuario añadió a `salida/puntuales/2026-11-18_CAMARA_CCIO/` la carpeta de fotos del CISE (68 imágenes, 1 video mp4 y un .docx que no es del evento), `pdf.jpg` (página impresa del 25-jul-2026, p. 5, Cartagena), `urls_instagram.txt` (10 enlaces, mismo orden que contenidos.txt) y `ig/` con 19 capturas de estadísticas de Instagram (2 por publicación, la última con 3). Solo hay capturas de 9 publicaciones, no de 10: por la miniatura y el orden, se dedujo (sin confirmar) que falta el reel nº 3 de contenidos.txt, "Emprendedor - Empresario". Las capturas de Instagram mezclan Instagram y Facebook en algunos reels (publicación cruzada). Aún no se ha armado el informe ni transcrito las capturas a CSV.

- 2026-11-18 (revisión 2): en `salida/puntuales/2026-11-18_CAMARA_CCIO/ig/` las capturas ya están renombradas `NN-k.jpeg` (NN = posición en `urls_instagram.txt` y orden de `contenidos.txt`; 10 publicaciones, 21 capturas, la 10 con 3). Se transcribió todo (la 03 es nueva): vistas IG totales 148.368 (informe general 01-06: 83.641; CISE 07-10: 64.727). Falta el alcance de la 09 y el tiempo promedio de la 08 y la 09 (no se ven en las capturas). Estilo de la presentación final: el PDF `NeuroReset · Informe de campaña Meta · Noviembre 2026.pdf` (9 diapositivas 16:9, fondo blanco roto, rojo El Universal, tipografía Inter, kicker rojo "01 · TÍTULO", un término del título en rojo, tarjetas gris claro, pie "<informe> · EL UNIVERSAL", cierre a pantalla roja). Logo del cliente: `logo_camara_comercio_500x500.webp` (azul índigo; sobre fondo rojo va en tarjeta blanca). Para ver el PDF se extrajeron sus imágenes con la biblioteca estándar (no hay visor de PDF instalado; la instalación de pymupdf fue denegada).

- 2026-11-18: Presentación del informe Cámara de Comercio (artefacto https://claude.ai/artifact/Ru71oQ7NMjh5kmeFg1vKk1, tipo Slides, 16 diapositivas, estilo NeuroReset: fondo #FCFCFD, tarjetas #F2F3F5, rojo #C8102E, tinta #14161A, Inter). Fuentes locales en `salida/puntuales/2026-11-18_CAMARA_CCIO/_deck/` (project/deck.json, deck.css, slides/*.html) y las imágenes subidas en `_assets_deck/`. Cifras: web 27 artículos, 17.983 vistas (general 10.398, CISE 7.585), usuarios únicos 7.315 / 5.742 y 12.456 sin duplicar (consulta conjunta `q4_total_27`, que dio 17.994 vistas por haberse hecho minutos después); Instagram 148.368 visualizaciones (general 83.641, CISE 64.727). Vista previa local con Edge headless en `_deck/_preview/` (no hay Playwright). Para republicar: Artifact con `url`, `root` = la carpeta `_deck`, `file_path` = un archivo cambiado, `files` = los demás.

- 2026-11-18: Repositorio público https://github.com/audiencias-eluniversal/data (sitio https://audiencias-eluniversal.github.io/data/; ya tenía `marfeel/informe-visitas-1a16nov26.html`). Se generó `marfeel/informe-camara-comercio-nov26.html` (4,4 MB, un solo HTML con las 16 diapositivas, imágenes en base64, sin notas del orador, `noindex`) con `salida/puntuales/2026-11-18_CAMARA_CCIO/_deck/exportar_html.py`. Commit hecho en un clon local (scratchpad `repo_data`), PERO el push falló: no hay credenciales de GitHub guardadas en este equipo (prompts desactivados). Pendiente que el usuario autentique y haga el push.

- 2026-11-18: Push hecho (commit 6413b71, main) tras iniciar sesión con git credential-manager: marfeel/informe-camara-comercio-nov26.html ya está en audiencias-eluniversal/data.

- 2026-11-18: Logo de El Universal (eu_rojo.svg) subido a la raíz de audiencias-eluniversal/data (commit 6abdcd9) y usado en el artefacto (v6) y en camara-comercio/informe-camara-comercio-nov26.html (enlace relativo ../eu_rojo.svg, no incrustado). Regla: usar siempre ese archivo como logo en informes del repo. README del repo actualizado.

## Kit para otro usuario: `kit_consultas/` (2026-11-18)

Carpeta autocontenida para que otra persona (el jefe del usuario) use su propio Claude Code y consulte Marfeel. Contiene `marfeel.py` (cliente: signin, límite de 1 petición/minuto, paginación, filas con comparación), `consultar.py` (URL o lista de URL, `--periodista <código>` que traduce el código de `periodistas.txt` a su id `tagFamily::filters`, `--desde/--hasta`, `--comparar previo|INICIO FIN`, `--agrupar`, `--sin-agrupar`, `--unicos`, `--filtro "campo op valor | valor2"`, `--metricas`, `--top`), `ejecutar_consulta.py` (ejecuta tal cual un cuerpo copiado de Explore, para aprender variables nuevas), `CLAUDE.md` (reglas, catálogo de variables confirmadas y protocolo: si falta una métrica/variable, pedir una consulta de prueba de Explore a la persona y deducir los nombres), `LEEME.md`, `verificar_entorno.ps1` (Python, pip, Git, Claude Code, Node opcional, requests, credenciales), `periodistas.txt` y `equipos.json` (copias), `ejemplos_explore/` (q01, q02, q03, q05, q06), `consultas_prueba/`, `credenciales.ejemplo.md`, `requirements.txt` y `.gitignore`. No incluye `credenciales.md` ni `token.json`: cada usuario pone las suyas (el límite de 1 petición/minuto es por cuenta). Probado el 2026-11-18: 2 URL de la Cámara (95 + 218 = 313 vistas, cuadra con el informe), `--unicos`, `--agrupar url medium`, filtro `url like`; periodista `spo` la semana 2-8 nov con `--comparar previo` (43.291 vistas contra 34.796, coincide en totales diarios sin agrupar y agrupado); `ejecutar_consulta.py` con `ejemplos_explore/q05` (30 filas). Corregido: la consola de Windows (cp1252) fallaba al imprimir `≥`; `marfeel.py` fuerza UTF-8. No probado: más de 100 URL (lotes) ni `--agrupar section`. Mantener este kit sincronizado si cambian las reglas de la API en este documento.

Ajuste del kit (2026-11-18): `kit_consultas/CLAUDE.md` tiene ahora un "Paso 0" que obliga a Claude a ejecutar `verificar_entorno.ps1` antes de cualquier consulta y a no seguir si falta Python, Git o credenciales (el script no instala nada; Claude propone el comando y lo ejecuta solo si la persona aprueba). `verificar_entorno.ps1` detecta el falso `python` de la Microsoft Store y se probó sin Python en el PATH (marca FALTA y deja `requests` como PENDIENTE).
