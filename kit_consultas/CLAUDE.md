# Consultar datos de Marfeel (El Universal): guía para Claude

Este kit saca métricas de Marfeel (páginas vistas, usuarios únicos, duración, fuentes de tráfico) del dominio `www.eluniversal.com.co`: por **URL o lista de URL**, por **periodista/equipo**, por **periodo**, con **filtros**, **agrupaciones** y **comparación contra otro periodo**. Lee esto entero antes de consultar. La persona que lo usa domina Marfeel Explore: cuando falte algo, pídele una consulta de prueba (ver "Cuando necesites algo que no está aquí").

## Paso 0, siempre primero: verifica el entorno (antes de cualquier consulta)

Esta persona puede no tener instalado lo necesario. **Al empezar una sesión, antes de lanzar ninguna consulta**, ejecuta:

```
powershell -ExecutionPolicy Bypass -File verificar_entorno.ps1
```

Comprueba Python 3.9+, pip, Claude Code, la librería `requests` y las credenciales (`credenciales.md`). Git y Node.js salen como opcionales: el kit no los usa. El script **no instala nada**: solo informa. Actúa así con el resultado:

- **Todo `[OK]`:** sigue con la consulta.
- **Falta Python o pip:** no sigas. Dile qué falta y dónde instalarlo (el script da el enlace). Si usa `winget`, puedes proponerle el comando (p. ej. `winget install Python.Python.3.12`) y ejecutarlo solo si lo aprueba. Tras instalar, **debe cerrar y volver a abrir la terminal** para que el PATH se actualice; luego repite la verificación. Ojo: en Windows, `python` puede ser un acceso directo a la Microsoft Store que no es Python real; el script ya lo detecta.
- **Falta `requests`:** ejecuta `pip install -r requirements.txt` (con su aprobación) y repite la verificación.
- **Faltan credenciales:** explícale que copie `credenciales.ejemplo.md` como `credenciales.md` y escriba ahí su correo y contraseña de Marfeel. Nunca le pidas que te las diga ni las muestres.
- No intentes "arreglar" instalaciones por tu cuenta ni correr los scripts hasta que la verificación pase.

## Herramientas (úsalas; no reescribas el cliente)

| Script | Para qué |
|---|---|
| `consultar.py` | Consulta por URL(s), periodista(s), periodo, filtros, agrupación y comparación. Es el de uso diario. |
| `ejecutar_consulta.py` | Ejecuta tal cual una consulta copiada de Explore (cuerpo JSON). Sirve para aprender variables nuevas. |
| `marfeel.py` | Cliente de la API (signin, límite, paginación, conversión a filas). Lo importan los otros. |
| `periodistas.txt` | `Periodista;Código;Grupo;Value`. El **Código** (con guion bajo, ej. `52k8j5v7_spo`) es el que conoce la persona; el **Value** es el id numérico que exige la API. |
| `equipos.json` | Equipos de trabajo y sus ids (referencia). |
| `ejemplos_explore/` | Cuerpos reales de consultas de Explore (totales con comparación, top de URL, fuentes de tráfico, secciones). Úsalos como plantilla. |
| `consultas_prueba/` | Donde la persona deja las consultas de prueba que copie de Explore. |

## Recetas

```
# URL o lista de URL (el archivo puede traer columnas, nombres, tabuladores: se extraen las http(s)://...)
python consultar.py --url <url>
python consultar.py --archivo urls.txt                                  # desde la fecha más antigua de las URL hasta hoy
python consultar.py --archivo urls.txt --desde 2026-11-01 --hasta 2026-11-15 --unicos
python consultar.py --archivo urls.txt --agrupar url medium             # fuentes de tráfico por URL

# Por periodista(s): basta el código de periodistas.txt; los traduce al id y filtra por tagFamily::filters (varios = OR)
python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --periodista 52k8j5v7_spo
python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --periodista 52k8j5v7_spo 02j2s7m0_etp --top 20

# Comparar periodos: `previo` (mismo largo, inmediatamente anterior) o fechas explícitas
python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --periodista 52k8j5v7_spo --comparar previo --sin-agrupar
python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --agrupar section --comparar 2026-10-26 2026-11-01 --top 20

# Filtros propios: "campo op valor [| valor2]"
python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --filtro "section eq 12" --filtro "url like loteria"

# Otras métricas
python consultar.py --archivo urls.txt --metricas pageViewsTotal averageDurationPerPage socialPosts
```

- **Salida:** `salida/<fecha_hora>/resultado.csv`, `consulta.json` (lo enviado) y `respuesta.json` (crudo). Con `--comparar`, cada métrica trae su columna `<métrica>_comparada`; la fila `TOTAL_CONSULTA` (o `TOTAL` sin agrupar) es el total de toda la consulta, no solo de las filas devueltas.
- **Comparar periodos con `groupBy url`:** un artículo publicado en el periodo actual vale 0 en el periodo comparado, porque no existía. Para comparar rendimiento entre periodos usa los **totales** (`--sin-agrupar`, o la fila TOTAL) o agrupa por algo que exista en ambos (`section`, `medium`).
- **Sin URL** se consulta todo el dominio (con `--desde` y `--hasta` obligatorios) y se piden solo las 50 primeras filas; usa `--top N` (hasta 500 por petición). Con lista de URL se traen todas las filas.
- **Fechas con URL:** por defecto desde la fecha más antigua de las URL (`/AAAA/MM/DD/`) hasta hoy. Antes de publicarse una URL no tiene visitas, así que usar la fecha más antigua para todas da lo mismo que usar la de cada una. Las URL sin fecha (portada, secciones) exigen `--desde`.
- Una URL que no aparece en el resultado se avisa como "SIN DATOS". Díselo a la persona; no la rellenes con ceros. Las URL que no son de El Universal (Instagram, Drive) no tienen datos en Marfeel: sepáralas antes.
- `--unicos` hace una petición más, sin agrupar, y da vistas y usuarios únicos **sin duplicar** del conjunto filtrado (también con comparación).

## Variables confirmadas (nombres exactos)

Solo se listan las que ya se usaron y funcionaron. Cualquier otra se debe confirmar con una consulta de Explore (ver más abajo); no las inventes: la API no avisa de nombres equivocados.

- **Métricas (`metrics`):** `pageViewsTotal` (vistas, sumables), `uniqueUsers` (usuarios únicos, **no sumables**), `averageDurationPerPage` (promedio, no se suma; el total es un promedio), `socialPosts` (publicaciones en redes por URL; por medium sale 0), `newArticles` (artículos nuevos; se usa sin agrupar, totales por día).
- **Agrupaciones (`groupBy`):** `url`, `medium` (fuente de tráfico), `section` (sección), y combinados `["url","medium"]`. Vacío `[]` = sin agrupar (serie por día).
- **Filtros (`filters[].filter`):** `domain` (siempre `www.eluniversal.com.co`), `url` (`eq` con una o varias URL completas; `like` = contiene), `section` (id numérico; `neq [0]` excluye páginas sin sección, como la portada), `tagFamily::filters` (doble `::`; ids numéricos de periodistas, ver `periodistas.txt`).
- **Operadores:** `eq`, `neq`, `like`. **Filtros distintos se combinan con AND; los valores dentro de un mismo filtro, con OR.** No hay OR entre filtros distintos (se probaron varias formas y la API las ignora en silencio).
- **Fechas:** `dates.range` `{start, end}` (AAAA-MM-DD, ambos incluidos), `dates.groupedBy: "daily"`. Comparación: `compare` `{start, end}`.
- **Mediums vistos:** `social`, `search`, `direct`, `referral`, `discover`, `gnews`, `facebook`, `taboola_news`, `(not set)`… (30 en una semana típica).
- **Ids de sección:** vienen como números en el filtro; en una respuesta agrupada por `section` aparece el nombre legible. Para filtrar por una sección concreta, pide la consulta de prueba en Explore y copia el id.

## Reglas que no se pueden saltar

1. **Límite de la API: 1 petición por minuto y 500 filas por respuesta, por cuenta.** Excederlo da HTTP 429 `Exceeded rate limit`. El cliente espera 65 s entre peticiones y reintenta. No lances consultas en paralelo ni pruebas de sondeo: cada una cuesta un minuto. Avisa del tiempo antes de lanzar varias (cada lote de 100 URL, cada `--unicos` y cada página de 500 filas es una petición).
2. **Credenciales: nunca las muestres, copies ni pegues en el chat o en otros archivos.** Están en `credenciales.md` (o variables `MARFEEL_EMAIL`/`MARFEEL_PASSWORD`). El token se guarda en `token.json`, vale 14 días y el cliente lo renueva si lo rechazan (401/403). Ambos están en `.gitignore`.
3. **La API no valida los filtros.** Un filtro mal escrito o de estructura desconocida se ignora en silencio y devuelve el total sin filtrar (o 200 con 0). Tras cualquier filtro nuevo, comprueba que el total tenga sentido: compáralo sin y con el filtro, y dilo.
4. **Usuarios únicos no se suman.** Un mismo usuario lee varios artículos; la suma por URL sobrestima. El total sin duplicar sale de una consulta **sin agrupar** (`--unicos`). Las vistas sí se suman.
5. **Los `medium` se solapan**: `discover` y `gnews` ⊂ `search`; `taboola_news` ⊂ `referral`; `facebook` ⊂ `social`. Nunca sumes mediums ni los uses como total; el total de una URL es su `pageViewsTotal` y el porcentaje de un medium va contra ese total (no suma 100 %).
6. **Las cifras cambian en vivo.** Dos consultas con minutos de diferencia pueden diferir en pocas visitas (visto: 439 vs 435). Indica fecha y hora del corte.
7. Si algo falla, no lo "arregles" cambiando cifras: informa el error exacto (HTTP y cuerpo). Un 500 en una consulta sin agrupar suele ser un `groupBy` ausente (debe ser `[]`) o un `order` en formato completo (sin agrupar es `{"metric": "...", "sort": "DESC"}`).

## Periodistas y equipos

- La persona conoce el **código** del periodista (`52k8j5v7_spo`). `--periodista <código>` lo busca en `periodistas.txt` y envía su id como `tagFamily::filters`. Si el código no está o no tiene `Value`, **no lo adivines**: pide una consulta de Explore con ese periodista (o la URL de Explore con el filtro puesto) para sacar el id y añade la fila a `periodistas.txt`.
- Un equipo = varios periodistas (columna `Grupo`; ids en `equipos.json`). Se consulta con todos sus códigos en `--periodista`. Ojo: **Deportes, Economía y Mundo** se definen por `section`, no por periodista, y **Web** además excluye una sección y ciertas URL (reglas en `equipos.json`; no replicadas en este kit). Hermes Figueroa Alcázar es el editor de Economía y un caso aparte. La composición de los equipos corresponde a noviembre de 2026.

## Cuando necesites algo que no está aquí (otra métrica, otra variable, otro filtro)

No lo adivines ni sondees la API a ciegas (cada intento cuesta un minuto). Pídele a la persona que arme la consulta en **Marfeel Explore** con lo que necesitas y te la pase:

1. En Explore, que configure la métrica/agrupación/filtro y ejecute la consulta.
2. Que copie el **cuerpo de la petición** (Chrome: F12 → Network → la petición `query` hacia `api.newsroom.bi` → pestaña Payload → *view source* → copiar) y lo pegue en `consultas_prueba/<nombre>.json`. También sirve la URL del Explore si trae el filtro (así se dedujeron los ids de los periodistas).
3. Ejecuta `python ejecutar_consulta.py consultas_prueba/<nombre>.json` (muestra métricas, `groupBy` y filtros que contiene) y lee el JSON para **deducir los nombres exactos**: `metrics`, `groupBy`, `filters[].filter`, `op`, forma de `value`. Si hay diferencias con lo que esperabas, pregunta antes de seguir.
4. Con esos nombres, usa `consultar.py --metricas …`/`--agrupar …`/`--filtro …`, o ejecuta el JSON con otras fechas (`--desde`/`--hasta`, `--comparar`). **Anota las variables nuevas confirmadas en la sección "Variables confirmadas" de este archivo** para la próxima vez.

## Presentación de resultados

Responde con cifras y su fecha de corte; indica cuántas URL se midieron, cuántas no tuvieron datos, qué filtros se aplicaron y qué periodo se comparó. Si se pide un informe visual, parte del `resultado.csv`. El logotipo de El Universal es `eu_rojo.svg` (raíz de https://github.com/audiencias-eluniversal/data).

## La API en crudo (por si necesitas algo que los scripts no cubren)

`POST https://api.newsroom.bi/api/dashboard/query`, cabecera `Authorization: Bearer <token>`:

```json
{"dates": {"groupedBy": "daily", "range": {"start": "2026-11-02", "end": "2026-11-08"}},
 "compare": {"start": "2026-10-26", "end": "2026-11-01"},
 "filters": [{"filter": "domain", "op": "eq", "value": ["www.eluniversal.com.co"]},
             {"filter": "tagFamily::filters", "op": "eq", "value": [7319363934]}],
 "groupBy": ["url"],
 "metrics": ["pageViewsTotal", "uniqueUsers"],
 "order": {"metric": "pageViewsTotal", "sort": "DESC", "type": "metric"},
 "granularity": "none", "discardOld": false, "from": 0, "limit": 500}
```

La respuesta es una lista con **una entrada por métrica**: `actualData.total`, `actualData.values[]` (`key`, `total`, `items[].value` = valor legible) y, si hubo `compare`, `compareData` con la misma forma. Los `key` coinciden entre métricas y así se unen. Sin `groupBy`, `actualData.data` trae la serie por día. `limit` máx. 500 y `from` es el desplazamiento; se corta cuando una página llega con menos filas que `limit`.
