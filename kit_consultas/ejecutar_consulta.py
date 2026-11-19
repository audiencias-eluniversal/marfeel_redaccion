"""Ejecuta una consulta COPIADA DE MARFEEL EXPLORE tal cual (el cuerpo JSON de la petición) y guarda CSV + JSON.

Sirve para aprender métricas, variables o filtros nuevos: la persona arma la consulta en Explore, copia el cuerpo de la
petición (Chrome: F12 > Network > petición `query` de api.newsroom.bi > pestaña Payload/Request > "view source" > copiar),
lo guarda en consultas_prueba/<nombre>.json y se ejecuta aquí. El nombre de cada métrica, groupBy y filtro queda a la vista.

Uso:
  python ejecutar_consulta.py consultas_prueba/mi_consulta.json
  python ejecutar_consulta.py consultas_prueba/mi_consulta.json --desde 2026-11-02 --hasta 2026-11-08   # cambia las fechas
  python ejecutar_consulta.py consultas_prueba/mi_consulta.json --todo                                  # pagina hasta traer todas las filas
Con --desde/--hasta, un `compare` existente se descarta (pásalo de nuevo con --comparar INICIO FIN).
Antes de ejecutar muestra un resumen: métricas, groupBy, filtros (campo + op + nº de valores) y fechas.
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import marfeel as m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("consulta")
    ap.add_argument("--desde")
    ap.add_argument("--hasta")
    ap.add_argument("--comparar", nargs=2, metavar=("INICIO", "FIN"))
    ap.add_argument("--todo", action="store_true")
    ap.add_argument("--salida")
    a = ap.parse_args()

    q = json.loads(Path(a.consulta).read_text(encoding="utf-8-sig"))
    if a.desde or a.hasta:
        r = q["dates"]["range"]
        r["start"], r["end"] = a.desde or r["start"], a.hasta or r["end"]
        q.pop("compare", None)
    if a.comparar:
        q["compare"] = {"start": a.comparar[0], "end": a.comparar[1]}
    q.setdefault("groupBy", [])  # sin agrupar hay que enviar groupBy: [] (si falta, HTTP 500)

    print("Consulta:")
    print(f"  fechas   : {q['dates']['range']['start']} a {q['dates']['range']['end']}"
          + (f"  | comparado {q['compare']['start']} a {q['compare']['end']}" if q.get("compare") else ""))
    print(f"  métricas : {q.get('metrics')}")
    print(f"  groupBy  : {q['groupBy']}")
    for f in q.get("filters", []):
        v = f.get("value")
        print(f"  filtro   : {f.get('filter')} {f.get('op')} ({len(v) if isinstance(v, list) else 1} valor/es)")

    resp = m.consultar_todo(q) if (a.todo and q["groupBy"]) else m.consultar(q)
    carpeta = Path(a.salida) if a.salida else m.BASE_DIR / "salida" / (datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_explore")
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "consulta.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta / "respuesta.json").write_text(json.dumps(resp, ensure_ascii=False, indent=1), encoding="utf-8")
    cab, filas = m.a_filas_agrupado(resp, q["groupBy"]) if q["groupBy"] else m.a_filas(resp)
    with open(carpeta / "resultado.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(filas)
    print(f"\n{len(filas) - 1} filas. Resultado: {carpeta / 'resultado.csv'}")
    print("Métricas devueltas por la API:", [x["metric"] for x in resp])


if __name__ == "__main__":
    try:
        main()
    except m.ErrorAPI as e:
        raise SystemExit(f"Error de la API de Marfeel: {e}")
