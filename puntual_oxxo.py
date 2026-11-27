"""Informe puntual de la marca OXXO: nota "OXXO llegó a la Heroica" (Informe Empresarial, 19 nov 2026).

Uso: python puntual_oxxo.py [--hasta 2026-11-23] [--forzar]

Consultas (4 peticiones, ~1 por minuto):
  q1_serie_diaria   la nota, sin agrupar: vistas, usuarios únicos, duración y publicaciones en redes por día
  q2_medium         la nota agrupada por medium (fuentes de tráfico; los mediums se solapan, no se suman)
  q3_notas_oxxo     todas las URL con "oxxo" Y "informe-empresarial" en el año (por si hay más contenido de la marca)
  q4_comparativo    URL de Informe Empresarial con visitas del 1 de nov a --hasta (para ubicar la nota)
Salida: salida/puntuales/<hasta>_OXXO/ (csv + json crudo por consulta, resumen.md y resumen.json).
"""
import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

import descargar as d

URL = "https://www.eluniversal.com.co/informe-empresarial/2026/11/19/oxxo-llego-a-la-heroica/"
INICIO = "2026-11-19"
DOMINIO = {"filter": "domain", "op": "eq", "value": ["www.eluniversal.com.co"]}


def base(inicio, fin, filtros, group_by, metricas, orden):
    q = {"dates": {"groupedBy": "daily", "range": {"start": inicio, "end": fin}},
         "filters": [DOMINIO] + filtros, "groupBy": group_by, "metrics": metricas,
         "granularity": "none", "discardOld": False, "from": 0, "limit": 500}
    q["order"] = ({"metric": orden, "sort": "DESC", "type": "metric"} if group_by else {"metric": orden, "sort": "DESC"})
    return q


def correr(carpeta, nombre, q, todo, forzar):
    ruta = carpeta / f"{nombre}.json"
    if ruta.exists() and not forzar:
        resp = json.loads(ruta.read_text(encoding="utf-8"))
    else:
        (carpeta / f"{nombre}_consulta.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
        resp = d.consultar_todo(q) if todo else d.consultar(q)
        ruta.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    cab, filas = d.a_filas_agrupado(resp, q["groupBy"]) if q["groupBy"] else d.a_filas(resp)
    with open(carpeta / f"{nombre}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(filas)
    return cab, filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hasta", default=date.today().isoformat())
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    carpeta = d.SALIDA / "puntuales" / f"{a.hasta}_OXXO"
    carpeta.mkdir(parents=True, exist_ok=True)
    url_f = {"filter": "url", "op": "eq", "value": [URL]}
    met = ["pageViewsTotal", "uniqueUsers", "averageDurationPerPage"]

    # 1) serie diaria de la nota
    cab1, f1 = correr(carpeta, "q1_serie_diaria",
                      base(INICIO, a.hasta, [url_f], [], met + ["socialPosts"], "pageViewsTotal"), False, a.forzar)
    # 2) fuentes de tráfico de la nota
    cab2, f2 = correr(carpeta, "q2_medium",
                      base(INICIO, a.hasta, [url_f], ["medium"], met, "pageViewsTotal"), False, a.forzar)
    # 3) todo el contenido de la marca en Informe Empresarial durante el año
    q3 = base("2026-01-01", a.hasta, [{"filter": "url", "op": "like", "value": ["oxxo"]},
                                       {"filter": "url", "op": "like", "value": ["informe-empresarial"]}],
              ["url"], met, "pageViewsTotal")
    cab3, f3 = correr(carpeta, "q3_notas_oxxo", q3, True, a.forzar)
    # 4) comparativo con el resto de Informe Empresarial
    q4 = base("2026-11-01", a.hasta, [{"filter": "url", "op": "like", "value": ["informe-empresarial"]}],
              ["url"], met, "pageViewsTotal")
    cab4, f4 = correr(carpeta, "q4_comparativo", q4, True, a.forzar)

    # ---- resumen ----
    tot1 = f1[-1]
    i1 = {c: n for n, c in enumerate(cab1)}
    dias = [r for r in f1[:-1]]
    ix4 = {c: n for n, c in enumerate(cab4)}
    notas = [r for r in f4[:-1] if re.search(r"/informe-empresarial/\d{4}/\d{2}/\d{2}/", r[ix4["url"]])]
    notas.sort(key=lambda r: -float(r[ix4["pageViewsTotal"]] or 0))
    pos = next((n for n, r in enumerate(notas, 1) if r[ix4["url"]] == URL), None)
    hoy = date.fromisoformat(a.hasta)
    nd = (hoy - date.fromisoformat(INICIO)).days + 1
    res = {
        "url": URL, "inicio": INICIO, "hasta": a.hasta, "dias": nd,
        "total": {c: tot1[i1[c]] for c in met + ["socialPosts"]},
        "por_dia": [{c: r[i1[c]] for c in ["fecha"] + met} for r in dias],
        "mediums": [dict(zip(cab2[1:], r[1:])) for r in f2[:-1]],
        "mediums_total_consulta": dict(zip(cab2[1:], f2[-1][1:])),
        "notas_oxxo_en_el_ano": [dict(zip(cab3[1:], r[1:])) for r in f3[:-1]],
        "comparativo": {"notas_informe_empresarial_con_visitas": len(notas), "posicion_oxxo": pos,
                        "mediana_vistas": sorted(float(r[ix4["pageViewsTotal"]] or 0) for r in notas)[len(notas) // 2] if notas else None,
                        "top5": [{"url": r[ix4["url"]], "vistas": r[ix4["pageViewsTotal"]], "usuarios": r[ix4["uniqueUsers"]]} for r in notas[:5]]},
    }
    (carpeta / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("total", "comparativo", "notas_oxxo_en_el_ano")}, ensure_ascii=False, indent=1))
    print(f"Peticiones: {d.ESTADISTICAS['peticiones']} (429: {d.ESTADISTICAS['http_429']})  Carpeta: {carpeta}")


if __name__ == "__main__":
    main()
