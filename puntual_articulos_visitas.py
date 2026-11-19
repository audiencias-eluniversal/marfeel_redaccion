"""Análisis puntual: artículos PUBLICADOS en un rango de fechas, agrupados por título, y cuántos
tienen menos de X visitas (por defecto 100, 500 y 1000).

Uso:  python puntual_articulos_visitas.py [--inicio 2026-11-01] [--fin 2026-11-16] [--umbrales 100 500 1000]
Salida: salida/puntuales/<inicio>_<fin>_articulos_por_visitas/ con
  articulos_publicados.csv/.json   (todas las filas, paginando de 500 en 500)
  resumen_umbrales.csv / .md       (conteo por umbral)
Si el CSV ya existe no vuelve a llamar a la API (use --forzar para repetir).
"""
import argparse
import csv
import json
from datetime import date

import descargar as d


def consulta(inicio: str, fin: str) -> dict:
    return {"dates": {"groupedBy": "daily", "range": {"end": fin, "start": inicio}},
            "filters": [{"filter": "domain", "op": "eq", "value": ["www.eluniversal.com.co"]},
                        {"filter": "publishDate", "op": "eq",
                         "value": [f"{inicio}T00:00:00_{fin}T23:59:00"]}],
            "groupBy": ["title"], "metrics": ["pageViewsTotal", "uniqueUsers"],
            "order": {"metric": "pageViewsTotal", "sort": "DESC", "type": "metric"},
            "granularity": "none", "discardOld": False, "from": 0, "limit": 50}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2026-11-01")
    ap.add_argument("--fin", default="2026-11-16")
    ap.add_argument("--umbrales", type=int, nargs="+", default=[100, 500, 1000])
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()

    carpeta = d.SALIDA / "puntuales" / f"{a.inicio}_{a.fin}_articulos_por_visitas"
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta_csv = carpeta / "articulos_publicados.csv"

    if a.forzar or not ruta_csv.exists():
        q = consulta(a.inicio, a.fin)
        (carpeta / "consulta.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
        resp = d.consultar_todo(q)
        (carpeta / "articulos_publicados.json").write_text(
            json.dumps(resp, ensure_ascii=False), encoding="utf-8")
        cab, filas = d.a_filas_agrupado(resp, q["groupBy"])
        with open(ruta_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(cab)
            w.writerows(filas)
    else:
        print("Ya existe articulos_publicados.csv: no se llama a la API.")

    with open(ruta_csv, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))
    total = next((r for r in filas if r["posicion"] == "TOTAL_CONSULTA"), None)
    arts = [r for r in filas if r["posicion"] != "TOTAL_CONSULTA"]
    vistas = [int(float(r["pageViewsTotal"] or 0)) for r in arts]
    n = len(arts)

    res = [("articulos_descargados", n, 100.0)]
    for u in sorted(a.umbrales):
        k = sum(1 for v in vistas if v < u)
        res.append((f"menos_de_{u}_visitas", k, round(k / n * 100, 1) if n else 0))
    with open(carpeta / "resumen_umbrales.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["concepto", "articulos", "porcentaje_del_total"])
        w.writerows(res)

    md = [f"# Artículos publicados del {a.inicio} al {a.fin}, por visitas", "",
          f"Filas descargadas (títulos distintos): **{n}**",
          f"Vistas totales de esos artículos (según la API): {total['pageViewsTotal'] if total else '-'}",
          f"Suma de las filas descargadas: {sum(vistas)}", "",
          "| Umbral | Artículos | % del total |", "|---|---|---|"]
    md += [f"| {c.replace('_', ' ')} | {k} | {p} % |" for c, k, p in res[1:]]
    md += ["", "Conteos con menos de X visitas (estricto, `<`) en `pageViewsTotal` del rango.",
           "La consulta agrupa por título: dos artículos con el mismo título se cuentan juntos."]
    (carpeta / "resumen_umbrales.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"Peticiones: {d.ESTADISTICAS['peticiones']} (429: {d.ESTADISTICAS['http_429']})")


if __name__ == "__main__":
    main()
