"""Análisis puntual por equipo: artículos PUBLICADOS en el rango, agrupados por título, con grupos de visitas
(<100, 100-499, 500-999, >=1000). Igual que puntual_articulos_visitas.py pero con el filtro de cada equipo
(config/equipos.json, vía descargar.aplicar_equipo). Omite los equipos cuyo CSV ya existe.
Uso: python puntual_equipos_visitas.py [--inicio 2026-11-01] [--fin 2026-11-16] [--equipos a b c] [--forzar]
Salida: salida/puntuales/<ini>_<fin>_articulos_por_visitas/equipos/<slug>/articulos_publicados.csv/.json
        y resumen_equipos.json en esa carpeta."""
import argparse, csv, json
import descargar as d
from puntual_articulos_visitas import consulta

EQUIPOS = ["sucesos", "entretenimiento", "locales", "web", "deportes", "economia", "mundo", "editor-economia"]
GRUPOS = [("<100", 0, 100), ("100-499", 100, 500), ("500-999", 500, 1000), (">=1000", 1000, float("inf"))]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2026-11-01"); ap.add_argument("--fin", default="2026-11-16")
    ap.add_argument("--equipos", nargs="+", default=EQUIPOS); ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    raiz = d.SALIDA / "puntuales" / f"{a.inicio}_{a.fin}_articulos_por_visitas"
    base_mes = d.SALIDA / "mensual" / "2026-11_01-16"
    resumen = {}
    for slug in a.equipos:
        car = raiz / "equipos" / slug; car.mkdir(parents=True, exist_ok=True)
        ruta = car / "articulos_publicados.csv"
        if a.forzar or not ruta.exists():
            q = d.aplicar_equipo(consulta(a.inicio, a.fin), slug, bases=[base_mes])
            (car / "consulta.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
            resp = d.consultar_todo(q)
            (car / "articulos_publicados.json").write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
            cab, filas = d.a_filas_agrupado(resp, q["groupBy"])
            with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f); w.writerow(cab); w.writerows(filas)
        with open(ruta, encoding="utf-8-sig", newline="") as f:
            filas = list(csv.DictReader(f))
        tot = next((r for r in filas if r["posicion"] == "TOTAL_CONSULTA"), None)
        v = [int(float(r["pageViewsTotal"] or 0)) for r in filas if r["posicion"] != "TOTAL_CONSULTA"]
        g = {n: {"articulos": sum(1 for x in v if lo <= x < hi), "visitas": sum(x for x in v if lo <= x < hi)} for n, lo, hi in GRUPOS}
        resumen[slug] = {"articulos": len(v), "visitas_suma": sum(v),
                         "visitas_api": float(tot["pageViewsTotal"]) if tot else None, "grupos": g}
        print(slug, resumen[slug]["articulos"], resumen[slug]["visitas_suma"], resumen[slug]["visitas_api"], flush=True)
        (raiz / "resumen_equipos.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Peticiones:", d.ESTADISTICAS["peticiones"], "429:", d.ESTADISTICAS["http_429"])

if __name__ == "__main__":
    main()
