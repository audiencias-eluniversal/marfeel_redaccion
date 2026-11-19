"""Consulta Marfeel de El Universal: por URL o lista de URL, por periodista, por periodo, con filtros,
agrupaciones y comparación contra otro periodo.

Ejemplos:
  python consultar.py --url https://www.eluniversal.com.co/cartagena/2026/11/10/algo-AB123/
  python consultar.py --archivo urls.txt                                   # desde la fecha más antigua de las URL hasta hoy
  python consultar.py --archivo urls.txt --desde 2026-11-01 --hasta 2026-11-15 --unicos
  python consultar.py --archivo urls.txt --agrupar url medium              # fuentes de tráfico por URL
  python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --periodista 52k8j5v7_spo 02j2s7m0_etp --comparar previo
  python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --agrupar section --comparar 2026-10-26 2026-11-01 --top 20
  python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --sin-agrupar --comparar previo   # totales y serie diaria
  python consultar.py --archivo urls.txt --metricas pageViewsTotal averageDurationPerPage
  python consultar.py --desde 2026-11-02 --hasta 2026-11-08 --filtro "section eq 12" --filtro "url like loteria"

Opciones principales
  --url / --archivo   URL (o texto con URL; se toma toda cadena http(s)://...). Opcionales: sin URL se consulta todo el dominio
                      (entonces --desde y --hasta son obligatorios y por defecto se piden solo las 50 primeras filas).
  --desde / --hasta   AAAA-MM-DD. Con URL, por defecto: la fecha más antigua de las URL (/AAAA/MM/DD/) y hoy.
  --periodista        uno o más códigos de periodistas.txt (ej. 52k8j5v7_spo); se traducen a su id de Marfeel y se envían
                      como filtro tagFamily::filters (varios = OR: artículos de cualquiera de ellos).
  --comparar          `previo` (el periodo inmediatamente anterior, de la misma duración) o `INICIO FIN`. Añade columnas _comparada.
  --agrupar           dimensiones del groupBy (por defecto url). Ej.: url | medium | section | url medium
  --sin-agrupar       sin groupBy: devuelve una fila por día + TOTAL.
  --unicos            además, una consulta sin agrupar: usuarios únicos/vistas del conjunto SIN duplicar (1 petición más).
  --filtro            "campo op valor [| valor2]" (repetible). op = eq | neq | like. AND entre filtros, OR entre valores.
                      Valores solo con dígitos se envían como número. La API NO valida filtros: comprueba los totales.
  --metricas          por defecto pageViewsTotal uniqueUsers. --orden: métrica de orden (por defecto la primera). --top N: solo N filas.

Salida: carpeta salida/<fecha_hora>/ con resultado.csv, consulta.json y respuesta.json (+ unicos_*.json).
Límite de Marfeel: 1 petición por minuto por cuenta; el script espera solo.
"""
import argparse
import csv
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import marfeel as m

URL_RE = re.compile(r"https?://[^\s\"'<>\t]+")
FECHA_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")
LOTE = 100  # URL por consulta (no se han probado lotes mayores)


def leer_urls(a):
    urls = list(a.url or [])
    if a.archivo:
        for linea in Path(a.archivo).read_text(encoding="utf-8-sig").splitlines():
            urls += URL_RE.findall(linea)
    return list(dict.fromkeys(u.strip() for u in urls if u.strip()))


def filtro_de(texto):
    partes = texto.split(None, 2)
    if len(partes) != 3 or partes[1] not in ("eq", "neq", "like"):
        raise SystemExit(f'Filtro mal escrito: "{texto}". Formato: "campo op valor [| valor2]" con op eq|neq|like')
    campo, op, resto = partes
    vals = [v.strip() for v in resto.split("|") if v.strip()]
    if campo not in ("url", "domain"):
        vals = [int(v) if v.isdigit() else v for v in vals]
    return {"filter": campo, "op": op, "value": vals}


def filtro_periodistas(codigos):
    tabla = m.periodistas()
    faltan = [c for c in codigos if c not in tabla]
    if faltan:
        raise SystemExit(
            f"Código(s) sin id de Marfeel en periodistas.txt: {faltan}. Añade la fila (columna Value = id) o pide a la persona "
            "una consulta de Explore con ese periodista para sacar el id del filtro tagFamily::filters.")
    return {"filter": "tagFamily::filters", "op": "eq", "value": [tabla[c] for c in codigos]}


def periodo_previo(desde, hasta):
    d, h = date.fromisoformat(desde), date.fromisoformat(hasta)
    dias = (h - d).days + 1
    return (d - timedelta(days=dias)).isoformat(), (d - timedelta(days=1)).isoformat()


def construir(urls, desde, hasta, metricas, group_by, extra, comparar, orden, limite):
    filtros = [{"filter": "domain", "op": "eq", "value": [m.DOMINIO]}]
    if urls:
        filtros.append({"filter": "url", "op": "eq", "value": urls})
    q = {"dates": {"groupedBy": "daily", "range": {"start": desde, "end": hasta}},
         "filters": filtros + extra, "groupBy": group_by,  # sin agrupar: groupBy [] explícito (si falta, HTTP 500)
         "metrics": metricas, "granularity": "none", "discardOld": False, "from": 0, "limit": limite}
    if comparar:
        q["compare"] = {"start": comparar[0], "end": comparar[1]}
    # sin agrupar el formato de orden es el simple; agrupado, el completo
    q["order"] = ({"metric": orden, "sort": "DESC", "type": "metric"} if group_by else {"metric": orden, "sort": "DESC"})
    return q


def csv_de(resp, group_by):
    return m.a_filas_agrupado(resp, group_by) if group_by else m.a_filas(resp)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", nargs="+")
    ap.add_argument("--archivo")
    ap.add_argument("--desde")
    ap.add_argument("--hasta")
    ap.add_argument("--periodista", nargs="+", default=[])
    ap.add_argument("--comparar", nargs="+", metavar="previo|INICIO FIN")
    ap.add_argument("--agrupar", nargs="+")
    ap.add_argument("--sin-agrupar", action="store_true")
    ap.add_argument("--unicos", action="store_true")
    ap.add_argument("--filtro", action="append", default=[])
    ap.add_argument("--metricas", nargs="+", default=["pageViewsTotal", "uniqueUsers"])
    ap.add_argument("--orden")
    ap.add_argument("--top", type=int)
    ap.add_argument("--salida")
    a = ap.parse_args()

    urls = leer_urls(a)
    fechas = [FECHA_RE.search(u) for u in urls]
    hasta = a.hasta or date.today().isoformat()
    if a.desde:
        desde = a.desde
    elif urls and all(fechas):
        desde = min(f"{f[1]}-{f[2]}-{f[3]}" for f in fechas)
    else:
        raise SystemExit("Indica --desde AAAA-MM-DD (sin URL, o con URL que no llevan fecha en la ruta).")
    if not urls and not a.hasta:
        raise SystemExit("Sin URL indica también --hasta AAAA-MM-DD.")

    comparar = None
    if a.comparar:
        if a.comparar == ["previo"]:
            comparar = periodo_previo(desde, hasta)
        elif len(a.comparar) == 2:
            comparar = tuple(a.comparar)
        else:
            raise SystemExit("--comparar admite `previo` o dos fechas: INICIO FIN")
        print(f"Periodo: {desde} a {hasta}; comparado con {comparar[0]} a {comparar[1]}.", flush=True)
        if urls:
            print("  Aviso: con URL, el periodo comparado solo tendrá datos de las URL publicadas antes de ese periodo.")

    extra = [filtro_de(f) for f in a.filtro]
    if a.periodista:
        extra.append(filtro_periodistas(a.periodista))
    group_by = [] if a.sin_agrupar else (a.agrupar or ["url"])
    orden = a.orden or a.metricas[0]
    limite = a.top or (m.LIMITE_FILAS if urls else 50)
    todo = bool(urls) and not a.top  # con lista de URL se traen todas las filas (pagina); sin URL, solo el top
    carpeta = Path(a.salida) if a.salida else m.BASE_DIR / "salida" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    carpeta.mkdir(parents=True, exist_ok=True)

    lotes = [urls[i:i + LOTE] for i in range(0, len(urls), LOTE)] or [[]]
    print(f"{len(urls)} URL, {desde} a {hasta}, agrupado por {group_by or 'nada'}, {len(lotes)} lote(s): "
          f"≥{len(lotes)} petición(es), ~1 por minuto.", flush=True)
    filas_tot, cab, consultas, respuestas = [], None, [], []
    for n, lote in enumerate(lotes, 1):
        q = construir(lote, desde, hasta, a.metricas, group_by, extra, comparar, orden, limite)
        resp = m.consultar_todo(q) if (todo and group_by) else m.consultar(q)
        consultas.append(q)
        respuestas.append(resp)
        cab, filas = csv_de(resp, group_by)
        filas_tot += filas if len(lotes) == 1 else [f for f in filas if f[0] not in ("TOTAL_CONSULTA", "TOTAL")]
        print(f"  lote {n}/{len(lotes)}: {len(filas) - 1} filas", flush=True)
    (carpeta / "consulta.json").write_text(json.dumps(consultas, ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta / "respuesta.json").write_text(json.dumps(respuestas, ensure_ascii=False), encoding="utf-8")

    with open(carpeta / "resultado.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cab[1:] if group_by else cab)
        # agrupado: se quita la columna `posicion`; la fila total conserva su etiqueta en la primera columna
        w.writerows(([r[0]] + r[2:] if r[0] == "TOTAL_CONSULTA" else r[1:]) if group_by else r for r in filas_tot)
    if urls and group_by and "url" in group_by:
        con = {r[cab.index("url")] for r in filas_tot if r[0] != "TOTAL_CONSULTA"}
        sin = [u for u in urls if u not in con]
        for u in sin:
            print(f"  SIN DATOS en Marfeel: {u}")
        print(f"  {len(con)} URL con datos, {len(sin)} sin datos.")

    if a.unicos:
        if len(lotes) > 1:
            print("  Aviso: hay más de un lote; los totales sin duplicar solo se calculan por lote.")
        for n, lote in enumerate(lotes, 1):
            qu = construir(lote, desde, hasta, a.metricas, [], extra, comparar, orden, m.LIMITE_FILAS)
            ru = m.consultar(qu)
            (carpeta / f"unicos_{n}.json").write_text(json.dumps(ru, ensure_ascii=False), encoding="utf-8")
            print(f"  Lote {n} sin duplicar: " + ", ".join(
                f"{x['metric']}={x['actualData']['total']}"
                + (f" (comparado {x['compareData']['total']})" if x.get("compareData") else "") for x in ru))

    print(f"\nListo: {carpeta / 'resultado.csv'}")
    if "medium" in group_by:
        print("Recuerda: los medium se solapan (discover ⊂ search, facebook ⊂ social); no los sumes.")


if __name__ == "__main__":
    try:
        main()
    except m.ErrorAPI as e:
        raise SystemExit(f"Error de la API de Marfeel: {e}")
