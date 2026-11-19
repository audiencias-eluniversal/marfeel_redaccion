"""Ejecuta una consulta de Marfeel (config/*.json) y guarda los resultados.

Uso:  python descargar.py config/q01_general.json
      python descargar.py config/q01_general.json --equipo entretenimiento
          (añade el filtro tagFamily::filters del equipo, definido en config/equipos.json,
          y guarda en salida/<semana>/equipos/<equipo>/)

Crea la carpeta  salida/YYYY-WNN_MM-DD/general  (semana ISO, lunes como inicio, WN con
2 dígitos; la fecha es el inicio del rango) y dentro guarda:
  <nombre_consulta>.csv   resultados (actual vs semana comparada)
  <nombre_consulta>.json  respuesta cruda de la API
"""
import csv
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

from auth import obtener_token

URL = "https://api.newsroom.bi/api/dashboard/query"
# Límite documentado por Marfeel: 1 petición por minuto por cuenta (compartido).
# 65 s es el margen que se recomienda en la práctica.
ESPERA_429 = 65
LIMITE_FILAS = 500  # máximo de filas por respuesta (documentado por Marfeel)
BASE_DIR = Path(__file__).parent
SALIDA = BASE_DIR / "salida"
EQUIPOS_JSON = BASE_DIR / "config" / "equipos.json"
_ultima_peticion = 0.0  # instante de la última petición, para respetar 1 por minuto
# Contadores de la sesión (los lee correr_periodo.py para el resumen).
ESTADISTICAS = {"peticiones": 0, "http_429": 0, "http_5xx": 0, "errores_red": 0, "token_renovado": 0}


class ErrorAPI(Exception):
    """Fallo de la API de Marfeel tras agotar reintentos, o error no reintentable (400...)."""

    def __init__(self, status, cuerpo):
        super().__init__(f"HTTP {status}: {cuerpo}")
        self.status = status
        self.cuerpo = cuerpo


def cargar_equipo(slug: str) -> dict:
    equipos = json.loads(EQUIPOS_JSON.read_text(encoding="utf-8"))
    if slug not in equipos:
        raise RuntimeError(f"Equipo '{slug}' no está en {EQUIPOS_JSON.name}: {list(equipos)}")
    return equipos[slug]


def _filtros_equipo(query: dict, slug: str) -> list:
    """Filtros del equipo (tagFamily, si lo tiene, + filtros_extra), sin la lista de URL excluidas."""
    equipo = cargar_equipo(slug)
    filtros = [f for f in query["filters"] if f["filter"] != "tagFamily::filters"]
    if equipo.get("tagFamily"):  # hay equipos definidos solo por filtros_extra (ej. Deportes)
        filtros.append({"filter": "tagFamily::filters", "op": "eq", "value": equipo["tagFamily"]})
    # Filtros adicionales propios del equipo (ej. excluir una sección con section neq <id>).
    return filtros + equipo.get("filtros_extra", [])


def bases_de_consulta(query: dict) -> list:
    """Carpetas base (salida/<semana ISO>) del rango y del comparado de una consulta.
    Solo para semanas; para meses u otros periodos se pasan `bases` explícitas."""
    inicios = [query["dates"]["range"]["start"]]
    if query.get("compare"):
        inicios.append(query["compare"]["start"])
    return [SALIDA / nombre_carpeta(i) for i in inicios]


def ruta_exclusiones_base(slug: str, base: Path) -> Path:
    return base / subcarpeta(slug) / "urls_excluidas.csv"


def ruta_exclusiones(slug: str, inicio: str) -> Path:
    return ruta_exclusiones_base(slug, SALIDA / nombre_carpeta(inicio))


def cargar_exclusiones(slug: str, query: dict, bases=None) -> list:
    """URL a excluir para los periodos de la consulta (rango + comparación).

    Se leen de <base del periodo>/equipos/<slug>/urls_excluidas.csv, una lista por periodo.
    Si el equipo define "exclusion_urls" y falta la lista de algún periodo, falla: seguir
    sin ella daría datos sin excluir sin avisar.
    """
    if "exclusion_urls" not in cargar_equipo(slug):
        return []
    urls = set()
    for base in bases or bases_de_consulta(query):
        ruta = ruta_exclusiones_base(slug, base)
        if not ruta.exists():
            raise RuntimeError(f"Falta {ruta}: genera antes la lista de exclusión de ese periodo.")
        with open(ruta, encoding="utf-8-sig") as f:
            urls |= {r["url"] for r in csv.DictReader(f)}
    return sorted(urls)


def generar_exclusiones(slug: str, base_query: dict, inicio: str, fin: str, base=None) -> Path:
    """Consulta (1 petición por cada 500 URL) las URL que cumplen la regla de exclusión del
    equipo en un periodo y las guarda en urls_excluidas.csv/.json de la carpeta del periodo."""
    regla = cargar_equipo(slug)["exclusion_urls"]
    filtros = _filtros_equipo(base_query, slug) + [
        {"filter": "section", "op": "eq", "value": [regla["seccion"]]},
        {"filter": "url", "op": "like", "value": regla["url_like_cualquiera"]},
        {"filter": "url", "op": "like", "value": regla["url_like_todos"]},
    ]
    consulta = {
        "dates": {"groupedBy": "daily", "range": {"start": inicio, "end": fin}},
        "filters": filtros, "groupBy": ["url"],
        "metrics": ["pageViewsTotal", "averageDurationPerPage"],
        "order": {"metric": "pageViewsTotal", "sort": "DESC"},
        "granularity": "none", "discardOld": False, "from": 0, "limit": LIMITE_FILAS,
    }
    filas, paginas = [], []
    while True:
        resp = consultar(consulta)
        paginas.append(resp)
        dur = {v["key"]: v["total"] for v in resp[1]["actualData"]["values"]}
        vals = resp[0]["actualData"]["values"]
        filas += [(v["items"][0]["value"], v["total"], dur.get(v["key"], "")) for v in vals]
        if len(vals) < LIMITE_FILAS:
            break
        consulta["from"] += LIMITE_FILAS
    ruta = ruta_exclusiones_base(slug, base) if base else ruta_exclusiones(slug, inicio)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["url", "pageViewsTotal", "averageDurationPerPage"])
        w.writerows(filas)
    ruta.with_suffix(".json").write_text(json.dumps(paginas, ensure_ascii=False), encoding="utf-8")
    print(f"Exclusiones {slug} {inicio}: {len(filas)} URL, {sum(f[1] for f in filas)} vistas", flush=True)
    return ruta


def aplicar_equipo(query: dict, slug, bases=None):
    """Devuelve la consulta con los filtros del equipo añadidos (tras el de dominio), y la
    lista de URL excluidas como `url neq [...]` si el equipo la define y no está vacía.
    Sin equipo devuelve la consulta tal cual (análisis general)."""
    if not slug:
        return query
    filtros = _filtros_equipo(query, slug)
    urls = cargar_exclusiones(slug, query, bases)
    if urls:  # una lista vacía enviada a la API podría ignorarse o devolver 0 sin avisar
        filtros.append({"filter": "url", "op": "neq", "value": urls})
    return dict(query, filters=filtros)


def subcarpeta(slug) -> str:
    return f"equipos/{slug}" if slug else "general"


def nombre_carpeta(inicio: str) -> str:
    d = date.fromisoformat(inicio)
    anio, semana, _ = d.isocalendar()  # semanas ISO: arrancan el lunes
    return f"{anio}-W{semana:02d}_{d:%m-%d}"


def carpeta_salida(inicio: str, subcarpeta: str = "general") -> Path:
    """salida/<semana>/<subcarpeta>. subcarpeta = "general" o "equipos/<equipo>"."""
    return SALIDA / nombre_carpeta(inicio) / subcarpeta


def consultar(query: dict):
    """POST con Bearer token. Respeta 1 petición/minuto, renueva el token si es rechazado
    (401/403) y reintenta los 429, 5xx y errores de red. Si agota los reintentos o recibe
    un error no reintentable (400...), lanza ErrorAPI con el estado y el cuerpo exacto."""
    global _ultima_peticion
    renovado = False
    ultimo_status, ultimo_cuerpo = None, ""
    for _ in range(6):
        falta = ESPERA_429 - (time.time() - _ultima_peticion)
        if _ultima_peticion and falta > 0:
            print(f"Espera {falta:.0f}s para respetar el límite de la API...", flush=True)
            time.sleep(falta)
        token = obtener_token(forzar=renovado)
        _ultima_peticion = time.time()
        ESTADISTICAS["peticiones"] += 1
        try:
            r = requests.post(
                URL, json=query, headers={"Authorization": f"Bearer {token}"}, timeout=120
            )
        except requests.RequestException as e:
            ESTADISTICAS["errores_red"] += 1
            ultimo_status, ultimo_cuerpo = "red", repr(e)[:300]
            print(f"Error de red ({e.__class__.__name__}), reintentando...", flush=True)
            time.sleep(ESPERA_429)
            continue
        if r.status_code in (401, 403) and not renovado:
            print("Token rechazado, renovando y reintentando...", flush=True)
            ESTADISTICAS["token_renovado"] += 1
            renovado = True
            continue
        if r.status_code == 429 or r.status_code >= 500:
            ESTADISTICAS["http_429" if r.status_code == 429 else "http_5xx"] += 1
            ultimo_status, ultimo_cuerpo = r.status_code, r.text[:500]
            pausa = int(r.headers.get("Retry-After", ESPERA_429))
            print(f"HTTP {r.status_code} ({ultimo_cuerpo[:80]}), reintentando en {pausa}s...", flush=True)
            time.sleep(pausa)
            continue
        if r.status_code >= 400:
            raise ErrorAPI(r.status_code, r.text[:500])
        return r.json()
    raise ErrorAPI(ultimo_status, ultimo_cuerpo)


def consultar_todo(query: dict):
    """Como consultar(), pero trae TODAS las filas: limit=500 y pagina con `from`.

    Entre páginas espera ESPERA_429 s (límite de 1 petición/minuto). Une los `values`
    de cada métrica (actual y comparado); los `total` son los de la primera página.
    """
    consulta = dict(query, limit=LIMITE_FILAS, **{"from": 0})
    union = None
    pagina = 0
    while True:
        if pagina:
            print(f"Pausa de {ESPERA_429}s (límite de la API)...")
            time.sleep(ESPERA_429)
        resp = consultar(consulta)
        pagina += 1
        n = max(
            len(f["values"])
            for m in resp
            for f in (m["actualData"], m.get("compareData"))
            if f
        )
        print(f"Página {pagina}: {n} filas (from={consulta['from']})")
        if union is None:
            union = resp
        else:
            for destino, nuevo in zip(union, resp):
                for campo in ("actualData", "compareData"):
                    if destino.get(campo) and nuevo.get(campo):
                        existentes = {v["key"] for v in destino[campo]["values"]}
                        destino[campo]["values"] += [
                            v for v in nuevo[campo]["values"] if v["key"] not in existentes
                        ]
        if n < LIMITE_FILAS:
            return union
        consulta["from"] += LIMITE_FILAS


def a_filas(respuesta: list):
    """Convierte la respuesta (una entrada por métrica) en filas alineadas por posición."""
    metricas = [m["metric"] for m in respuesta]
    actual, comparado = {}, {}
    fechas_act, fechas_cmp = [], []
    for m in respuesta:
        nombre = m["metric"]
        for fuente, destino, fechas in (
            (m["actualData"], actual, fechas_act),
            (m.get("compareData"), comparado, fechas_cmp),
        ):
            if not fuente:
                continue
            serie = []
            for punto in fuente["data"]:
                clave = next(k for k in punto if k != "label")
                serie.append((punto["label"], punto[clave]))
            destino[nombre] = [v for _, v in serie]
            if len(fechas) < len(serie):
                fechas[:] = [l for l, _ in serie]

    cabecera = ["fecha", "fecha_comparada"]
    for n in metricas:
        cabecera += [n, f"{n}_comparada"]
    filas = []
    for i, f in enumerate(fechas_act):
        fila = [f[:10], fechas_cmp[i][:10] if i < len(fechas_cmp) else ""]
        for n in metricas:
            fila.append(actual[n][i] if i < len(actual.get(n, [])) else "")
            fila.append(comparado[n][i] if i < len(comparado.get(n, [])) else "")
        filas.append(fila)
    total = ["TOTAL", ""]
    for m in respuesta:
        total.append(m["actualData"]["total"])
        total.append((m.get("compareData") or {}).get("total", ""))
    filas.append(total)
    return cabecera, filas


def a_filas_agrupado(respuesta: list, group_by: list):
    """Una fila por elemento del groupBy (ej. url, medium) con el total de cada métrica.

    Los elementos se unen entre métricas por su 'key'. Si la consulta trae `compare`,
    se añade una columna <métrica>_comparada con el valor del periodo comparado
    (vacío si el elemento no aparece en ese periodo). La última fila es el total de la
    consulta completa (no solo del top devuelto).
    """
    metricas = [m["metric"] for m in respuesta]
    con_comparacion = any(m.get("compareData") for m in respuesta)
    elementos = {}  # key -> valores legibles del groupBy
    actual = {n: {} for n in metricas}
    comparado = {n: {} for n in metricas}
    for m in respuesta:
        for fuente, destino in ((m["actualData"], actual), (m.get("compareData"), comparado)):
            if not fuente:
                continue
            for v in fuente["values"]:
                elementos.setdefault(v["key"], [i["value"] for i in v["items"]])
                destino[m["metric"]][v["key"]] = v["total"]

    cabecera = ["posicion"] + list(group_by)
    for n in metricas:
        cabecera.append(n)
        if con_comparacion:
            cabecera.append(f"{n}_comparada")
    filas = []
    for pos, (clave, dims) in enumerate(elementos.items(), start=1):
        dims = (dims + [""] * len(group_by))[: len(group_by)]
        fila = [pos] + dims
        for n in metricas:
            fila.append(actual[n].get(clave, ""))
            if con_comparacion:
                fila.append(comparado[n].get(clave, ""))
        filas.append(fila)
    total = ["TOTAL_CONSULTA"] + [""] * len(group_by)
    for m in respuesta:
        total.append(m["actualData"]["total"])
        if con_comparacion:
            total.append((m.get("compareData") or {}).get("total", ""))
    filas.append(total)
    return cabecera, filas


def ejecutar(query: dict, nombre: str, base: Path, equipo=None, bases=None, todo=False) -> Path:
    """Ejecuta una consulta y guarda <base>/<general|equipos/slug>/<nombre>.csv y .json.

    `base` es la carpeta del periodo (semana o mes). `bases` son las carpetas del rango y
    del comparado, de donde se leen las listas de exclusión del equipo (si las hay)."""
    consulta = aplicar_equipo(query, equipo, bases)
    carpeta = base / subcarpeta(equipo)
    carpeta.mkdir(parents=True, exist_ok=True)

    respuesta = consultar_todo(consulta) if todo else consultar(consulta)
    (carpeta / f"{nombre}.json").write_text(
        json.dumps(respuesta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if consulta.get("groupBy"):
        cabecera, filas = a_filas_agrupado(respuesta, consulta["groupBy"])
    else:
        cabecera, filas = a_filas(respuesta)
    with open(carpeta / f"{nombre}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cabecera)
        w.writerows(filas)
    print(f"Guardado en {carpeta}", flush=True)
    return carpeta / f"{nombre}.csv"


def main(ruta_config: str, todo: bool = False, equipo=None):
    ruta = Path(ruta_config)
    query = json.loads(ruta.read_text(encoding="utf-8"))
    bases = bases_de_consulta(query)  # semanas ISO por fecha de inicio
    ejecutar(query, ruta.stem, bases[0], equipo, bases, todo)


if __name__ == "__main__":
    args = sys.argv[1:]
    equipo = None
    if "--equipo" in args:
        i = args.index("--equipo")
        equipo = args[i + 1]
        del args[i : i + 2]
    todo = "--todo" in args
    args = [a for a in args if a != "--todo"]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], todo=todo, equipo=equipo)
