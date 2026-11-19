"""Traffic medium de cada URL del top (q02) de una semana, en pocas peticiones.

Uso:  python medium_por_url.py config/q02_articulos.json
      python medium_por_url.py config/q02_articulos_semana_anterior.json
      python medium_por_url.py config/q02_articulos.json --equipo entretenimiento
      python medium_por_url.py config/q02_articulos.json --sin-api   (regenera el CSV
          desde el .json ya guardado, sin gastar peticiones)

IMPORTANTE: los mediums NO son excluyentes (ej. discover está dentro de search,
facebook dentro de social), por eso la suma de mediums supera el total de la URL.
Nunca sumar mediums; el porcentaje se calcula sobre el total real de la URL (q02).

Lee el CSV del top de URL de esa consulta (salida/<semana>/<q02>.csv), consulta
a Marfeel TODAS esas URL de una vez con groupBy ["url","medium"] (paginando de
500 en 500 filas, 65 s entre peticiones por el límite de 1 petición/minuto) y
guarda en la misma carpeta de la semana:
  q03_medium_<nombre>.csv    una fila por (url, medium)
  q03_medium_<nombre>.json   respuestas crudas de cada página

Clasificación de cada URL (columna tipo_url):
  home      raíz del dominio
  tag       ruta con /tags/ o /tag/ (agrupación de artículos por temática)
  articulo  ruta con fecha /YYYY/MM/DD/
  seccion   cualquier otra ruta (incluye subsecciones)
"""
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from descargar import aplicar_equipo, bases_de_consulta, consultar, subcarpeta

LIMITE = 500  # máximo de filas por respuesta (documentado por Marfeel)
RE_FECHA = re.compile(r"/\d{4}/\d{2}/\d{2}/")


def clasificar(url: str):
    """Devuelve (tipo_url, seccion). seccion = ruta antes de la fecha o la ruta misma."""
    ruta = urlparse(url).path
    if ruta in ("", "/"):
        return "home", ""
    if re.search(r"/tags?/", ruta):
        return "tag", ruta.strip("/")
    m = RE_FECHA.search(ruta)
    if m:
        return "articulo", ruta[: m.start()].strip("/")
    return "seccion", ruta.strip("/")


def ejecutar(base_query: dict, nombre_top: str, base: Path, equipo=None, bases=None, sin_api=False):
    """Medium de las URL del top `nombre_top` (CSV de la carpeta del periodo `base`).
    Guarda q03_medium_<...>.csv/.json junto al top. Devuelve la ruta del CSV."""
    consulta_base = aplicar_equipo(base_query, equipo, bases)
    carpeta = base / subcarpeta(equipo)
    csv_top = carpeta / f"{nombre_top}.csv"
    nombre = nombre_top.replace("q02_", "q03_medium_", 1)

    top = []  # (posicion, url, pageViewsTotal del top)
    with open(csv_top, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["posicion"] != "TOTAL_CONSULTA":
                top.append((int(r["posicion"]), r["url"], r["pageViewsTotal"]))
    urls = [u for _, u, _ in top]
    print(f"{len(urls)} URL leídas de {csv_top.name}")

    if not urls:  # top vacío: no hay nada que consultar (un filtro url con lista vacía engaña)
        with open(carpeta / f"{nombre}.csv", "w", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerow(["posicion_url", "url", "tipo_url", "seccion", "medium"])
        print("Top vacío: CSV de medium vacío", flush=True)
        return carpeta / f"{nombre}.csv"

    # Filtros originales (dominio y, si hay, equipo) + las URL del top.
    filtros = [f for f in consulta_base["filters"] if f["filter"] != "url"]
    filtros.append({"filter": "url", "op": "eq", "value": urls})
    consulta = {
        "dates": consulta_base["dates"],
        "filters": filtros,
        "groupBy": ["url", "medium"],
        "metrics": consulta_base["metrics"],
        "order": consulta_base["order"],
        "granularity": "none",
        "discardOld": False,
        "from": 0,
        "limit": LIMITE,
    }

    paginas, filas_pagina = [], []
    desde = 0
    if sin_api:
        paginas = json.loads((carpeta / f"{nombre}.json").read_text(encoding="utf-8"))
        print(f"Usando respuestas guardadas ({len(paginas)} páginas), sin llamar a la API")
    while not sin_api:
        consulta["from"] = desde  # consultar() ya espacia las peticiones (1/min)
        resp = consultar(consulta)
        paginas.append(resp)
        n = len(resp[0]["actualData"]["values"])
        filas_pagina.append(n)
        print(f"Página {len(paginas)}: {n} filas (from={desde})")
        if n < LIMITE:
            break
        desde += LIMITE

    metricas = [m["metric"] for m in paginas[0]]
    combos = {}  # key -> {"url","medium", metrica: total}
    for resp in paginas:
        for m in resp:
            for v in m["actualData"]["values"]:
                c = combos.setdefault(
                    v["key"],
                    {"url": v["items"][0]["value"], "medium": v["items"][1]["value"]},
                )
                c[m["metric"]] = v["total"]

    posicion = {u: p for p, u, _ in top}
    pv_top = {u: float(pv) for _, u, pv in top}
    # Suma de mediums solo para control: NO es el total (los mediums se solapan).
    suma_pv = {}
    for c in combos.values():
        suma_pv[c["url"]] = suma_pv.get(c["url"], 0) + (c.get("pageViewsTotal") or 0)

    filas = []
    for c in combos.values():
        tipo, seccion = clasificar(c["url"])
        total_url = pv_top.get(c["url"], 0)  # total real de la URL (q02)
        pv = c.get("pageViewsTotal", 0)
        filas.append(
            [posicion.get(c["url"], ""), c["url"], tipo, seccion, c["medium"]]
            + [c.get(n, "") for n in metricas]
            + [round(pv / total_url * 100, 2) if total_url else ""]
        )
    filas.sort(key=lambda r: (r[0] if r[0] != "" else 10**6, -(r[5] or 0)))

    cabecera = (
        ["posicion_url", "url", "tipo_url", "seccion", "medium"]
        + metricas
        + ["pct_vistas_url"]
    )
    with open(carpeta / f"{nombre}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cabecera)
        w.writerows(filas)
    (carpeta / f"{nombre}.json").write_text(
        json.dumps(paginas, ensure_ascii=False), encoding="utf-8"
    )

    # Controles de calidad
    urls_resp = {c["url"] for c in combos.values()}
    faltan = [u for u in urls if u not in urls_resp]
    print(f"Guardado: {carpeta / (nombre + '.csv')}")
    print(f"Filas: {len(filas)} | URL con datos: {len(urls_resp)}/{len(urls)}")
    if faltan:
        print("URL sin datos:", faltan)
    # Control: la suma de mediums nunca debería ser MENOR que el total de la URL.
    menores = [
        (u, pv_top[u], suma_pv[u]) for u in urls_resp if suma_pv[u] < pv_top[u] * 0.99
    ]
    if menores:
        print("URL cuya suma de mediums es menor que su total (revisar):", menores)
    return carpeta / f"{nombre}.csv"


def main(ruta_config: str, sin_api: bool = False, equipo=None):
    ruta = Path(ruta_config)
    query = json.loads(ruta.read_text(encoding="utf-8"))
    bases = bases_de_consulta(query)  # semanas ISO por fecha de inicio
    ejecutar(query, ruta.stem, bases[0], equipo, bases, sin_api)


if __name__ == "__main__":
    args = sys.argv[1:]
    equipo = None
    if "--equipo" in args:
        i = args.index("--equipo")
        equipo = args[i + 1]
        del args[i : i + 2]
    sin_api = "--sin-api" in args
    args = [a for a in args if a != "--sin-api"]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], sin_api=sin_api, equipo=equipo)
