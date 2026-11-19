"""Métricas de Marfeel (páginas vistas y usuarios únicos) de los artículos de El Universal listados en
una carpeta de `salida/puntuales/<...>/contenidos.txt` (informe Cámara de Comercio de Cartagena).

Uso: python puntual_contenidos_camara.py [--carpeta salida/puntuales/2026-11-18_CAMARA_CCIO] [--hasta 2026-11-18] [--forzar]

Cómo se mide: cada URL se mide desde la fecha que lleva en su ruta (/AAAA/MM/DD/) hasta `--hasta`.
Una sola consulta con todas las URL (filtro `url eq` con varios valores, OR) agrupada por URL usa como
inicio la fecha más antigua: antes de su publicación una URL no tiene visitas, así que el resultado es
el mismo que con su propia fecha. Una consulta de control con la fecha propia de una URL lo comprueba.
Los usuarios únicos NO se suman entre artículos: se piden aparte por bloque (sin agrupar) para tener el dato sin duplicados.

Salida (en la carpeta): metricas_marfeel.csv, resumen.md, resumen.json, consultas/ (consulta y respuesta cruda de cada petición),
redes_y_drive.csv (enlaces que no son de El Universal, sin métricas).
"""
import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path

import descargar as d

DOMINIO = {"filter": "domain", "op": "eq", "value": ["www.eluniversal.com.co"]}
MARCA_SECCION = "Cubrimiento especial apertura CISE Santa Rosa"
URL_RE = re.compile(r"https?://\S+")


def leer_contenidos(ruta: Path):
    """Devuelve la lista de ítems. Una entrada puede ocupar 2 líneas (comillas con salto de línea)."""
    texto = ruta.read_text(encoding="utf-8-sig")
    items, seccion, pendiente = [], "Informe general", None
    for linea in texto.splitlines()[1:]:
        if not linea.strip():
            continue
        if linea.lstrip().startswith("--") and MARCA_SECCION.lower() in linea.lower():
            seccion = MARCA_SECCION
            continue
        m = URL_RE.search(linea)
        if m:
            partes = linea.split("\t")
            if len(partes) >= 3 and partes[0].strip().isdigit():
                num, nombre = int(partes[0]), partes[1].strip()
            elif pendiente:  # la 2.ª línea de una entrada partida: "<comillas>\t<url>"
                num, nombre = pendiente
            else:
                continue
            pendiente = None
            nombre = nombre.strip('" ')
            items.append({"num": num, "nombre": nombre, "url": m.group(0).strip(), "seccion": seccion})
        else:  # 1.ª línea de una entrada partida: "<n>\t<nombre entre comillas sin cerrar>"
            partes = linea.split("\t")
            if len(partes) >= 2 and partes[0].strip().isdigit():
                pendiente = (int(partes[0]), partes[1])
    return items


def tipo_de(url: str) -> str:
    if "eluniversal.com.co" in url:
        return "marfeel"
    if "instagram.com" in url:
        return "instagram"
    if "drive.google.com" in url:
        return "drive"
    return "otro"


def fecha_de_url(url: str):
    m = re.search(r"/(\d{4})/(\d{2})/(\d{2})/", url)
    return date(int(m[1]), int(m[2]), int(m[3])) if m else None


def consulta(urls, inicio, fin, agrupar):
    q = {"dates": {"groupedBy": "daily", "range": {"start": inicio, "end": fin}},
         "filters": [DOMINIO, {"filter": "url", "op": "eq", "value": urls}],
         "metrics": ["pageViewsTotal", "uniqueUsers"],
         "order": {"metric": "pageViewsTotal", "sort": "DESC", "type": "metric"},
         "granularity": "none", "discardOld": False, "from": 0, "limit": 500}
    # Sin agrupar, la API de Marfeel exige `groupBy: []` explícito (sin él devolvió HTTP 500) y el mismo
    # formato de orden que q01_general.json.
    q["groupBy"] = ["url"] if agrupar else []
    if not agrupar:
        q["order"] = {"metric": "uniqueUsers", "sort": "DESC"}
    return q


def guardar(carpeta, nombre, q, resp):
    (carpeta / f"{nombre}_consulta.json").write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
    (carpeta / f"{nombre}_respuesta.json").write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--carpeta", default=str(d.SALIDA / "puntuales" / "2026-11-18_CAMARA_CCIO"))
    ap.add_argument("--hasta", default=date.today().isoformat())
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()
    carpeta = Path(a.carpeta)
    cons = carpeta / "consultas"
    cons.mkdir(parents=True, exist_ok=True)

    items = leer_contenidos(carpeta / "contenidos.txt")
    for it in items:
        it["tipo"] = tipo_de(it["url"])
        f = fecha_de_url(it["url"]) if it["tipo"] == "marfeel" else None
        it["fecha_url"] = f.isoformat() if f else ""
    art = [i for i in items if i["tipo"] == "marfeel"]
    otros = [i for i in items if i["tipo"] != "marfeel"]
    print(f"{len(items)} ítems: {len(art)} de El Universal, {len(otros)} otros (redes/Drive).", flush=True)

    inicio = min(i["fecha_url"] for i in art)
    urls = [i["url"] for i in art]

    # 1) una consulta agrupada por URL
    ruta_resp = cons / "q1_por_url_respuesta.json"
    if ruta_resp.exists() and not a.forzar:
        resp = json.loads(ruta_resp.read_text(encoding="utf-8"))
    else:
        q = consulta(urls, inicio, a.hasta, True)
        resp = d.consultar_todo(q)
        guardar(cons, "q1_por_url", q, resp)
    cab, filas = d.a_filas_agrupado(resp, ["url"])
    ix = {c: n for n, c in enumerate(cab)}
    datos = {}
    for r in filas:
        if r[ix["posicion"]] == "TOTAL_CONSULTA":
            continue
        datos[r[ix["url"]]] = (float(r[ix["pageViewsTotal"]] or 0), float(r[ix["uniqueUsers"]] or 0))

    # 2) usuarios únicos sin duplicados, por bloque (consulta sin agrupar)
    bloques = {}
    for nombre in ("Informe general", MARCA_SECCION):
        u = [i["url"] for i in art if i["seccion"] == nombre]
        if not u:
            continue
        ini = min(fecha_de_url(x) for x in u).isoformat()
        clave = "q2_" + ("general" if nombre == "Informe general" else "cise")
        ruta_b = cons / f"{clave}_respuesta.json"
        if ruta_b.exists() and not a.forzar:
            rb = json.loads(ruta_b.read_text(encoding="utf-8"))
        else:
            qb = consulta(u, ini, a.hasta, False)
            rb = d.consultar(qb)
            guardar(cons, clave, qb, rb)
        bloques[nombre] = {"inicio": ini, "n": len(u),
                           "pv": rb[0]["actualData"]["total"], "uu": rb[1]["actualData"]["total"]}

    # 3) control: una URL con su propia fecha (la más reciente) debe dar lo mismo que la consulta agrupada
    control = max(art, key=lambda i: i["fecha_url"])
    ruta_c = cons / "q3_control_respuesta.json"
    if ruta_c.exists() and not a.forzar:
        rc = json.loads(ruta_c.read_text(encoding="utf-8"))
    else:
        qc = consulta([control["url"]], control["fecha_url"], a.hasta, False)
        rc = d.consultar(qc)
        guardar(cons, "q3_control", qc, rc)
    ctrl = (rc[0]["actualData"]["total"], rc[1]["actualData"]["total"])
    esperado = datos.get(control["url"])

    # salida unificada
    hoy = date.fromisoformat(a.hasta)
    with open(carpeta / "metricas_marfeel.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["num", "seccion", "nombre", "url", "fecha_url", "dias_hasta_hoy", "pageViewsTotal", "uniqueUsers", "estado"])
        for i in art:
            pv, uu = datos.get(i["url"], (None, None))
            dias = (hoy - date.fromisoformat(i["fecha_url"])).days
            w.writerow([i["num"], i["seccion"], i["nombre"], i["url"], i["fecha_url"], dias,
                        "" if pv is None else int(pv), "" if uu is None else int(uu),
                        "OK" if pv is not None else "SIN DATOS EN MARFEEL"])
    with open(carpeta / "redes_y_drive.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["num", "seccion", "nombre", "url", "tipo", "metricas"])
        for i in otros:
            w.writerow([i["num"], i["seccion"], i["nombre"], i["url"], i["tipo"], "pendiente"])

    sin = [i for i in art if i["url"] not in datos]
    por_sec = {}
    for i in art:
        s = por_sec.setdefault(i["seccion"], {"articulos": 0, "pv": 0})
        s["articulos"] += 1
        s["pv"] += int(datos.get(i["url"], (0, 0))[0])
    res = {"hasta": a.hasta, "articulos": len(art), "otros_enlaces": len(otros), "sin_datos": [i["url"] for i in sin],
           "por_seccion_suma": por_sec, "bloques_sin_duplicar": bloques,
           "control": {"url": control["url"], "fecha": control["fecha_url"], "propia": ctrl, "agrupada": esperado}}
    (carpeta / "resumen.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")

    md = [f"# Métricas Marfeel — contenidos Cámara de Comercio (hasta {a.hasta})", "",
          f"Artículos de El Universal: {len(art)}. Enlaces de redes/Drive sin métricas de Marfeel: {len(otros)}.", ""]
    for s, v in por_sec.items():
        b = bloques.get(s, {})
        md.append(f"- **{s}**: {v['articulos']} artículos; suma de páginas vistas {v['pv']:,}; "
                  f"consulta del bloque sin agrupar: {b.get('pv')} vistas y {b.get('uu')} usuarios únicos (sin duplicar).".replace(",", "."))
    md += ["", f"Control: {control['url']} desde {control['fecha_url']}: {ctrl} (vistas, usuarios) contra {esperado} en la consulta agrupada.",
           f"Sin datos: {len(sin)}"]
    (carpeta / "resumen.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    print(f"Peticiones: {d.ESTADISTICAS['peticiones']} (429: {d.ESTADISTICAS['http_429']})")


if __name__ == "__main__":
    main()
