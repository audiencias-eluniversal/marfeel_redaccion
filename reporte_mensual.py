"""Genera el reporte HTML del análisis mensual (general + selector de equipos).

Uso:  python reporte_mensual.py [--mes 2026-11_01-16] [--previo 2026-10_01-16]
Lee los CSV/JSON ya descargados (no llama a la API) y escribe
salida/mensual/<mes>/reporte_mensual.html, un archivo único con los datos incrustados.
Los gráficos usan Chart.js desde cdnjs (necesita conexión al abrirlo).
"""
import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).parent
MENSUAL = RAIZ / "salida" / "mensual"
HOME = "https://www.eluniversal.com.co"
MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
EQUIPOS = [("general", "General (toda la redacción)"), ("entretenimiento", "Entretenimiento"),
           ("sucesos", "Sucesos"), ("locales", "Locales"), ("web", "Web"),
           ("monetizacion", "Monetización"), ("deportes", "Deportes"),
           ("editor-economia", "Editor Economía"), ("economia", "Economía"), ("mundo", "Mundo")]


def etiqueta(carpeta: str) -> str:
    """'2026-11_01-16' -> '1-16 nov 2026'."""
    m = re.match(r"(\d{4})-(\d{2})_(\d{2})-(\d{2})", carpeta)
    a, mes, d1, d2 = m.groups()
    return f"{int(d1)}-{int(d2)} {MESES[int(mes)]} {a}"


def num(x):
    try:
        f = float(x)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return 0


def leer_csv(ruta: Path):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def titulo_de_url(url: str, tipo: str) -> str:
    if url.rstrip("/") == HOME:
        return "Home"
    ruta = [p for p in urlparse(url).path.split("/") if p]
    if tipo == "seccion" or not ruta:
        return "Sección: " + " / ".join(p.replace("-", " ") for p in ruta)
    slug = ruta[-1].replace("-", " ")
    return slug[:1].upper() + slug[1:]


def seccion_de_url(url: str) -> str:
    ruta = [p for p in urlparse(url).path.split("/") if p]
    return ruta[0] if ruta else ""


def totales_q01(ruta: Path):
    d = json.loads(ruta.read_text(encoding="utf-8"))
    out = {}
    for m in d:
        cmp_ = m.get("compareData") or {}
        out[m["metric"]] = {"actual": m.get("total"), "previo": cmp_.get("total")}
    return out


def periodo_top(carpeta: Path):
    """Top de URL con su distribución por medio (q03). Devuelve (filas, total_vistas)."""
    q02 = leer_csv(carpeta / "q02_articulos.csv")
    q03 = leer_csv(carpeta / "q03_medium_articulos.csv")
    medios = {}
    tipos = {}
    for r in q03:
        medios.setdefault(r["url"], []).append(
            {"m": r["medium"], "v": num(r["pageViewsTotal"]), "p": num(r["pct_vistas_url"])})
        tipos[r["url"]] = r["tipo_url"]
    filas, total = [], 0
    for r in q02:
        if r["posicion"] == "TOTAL_CONSULTA":
            total = num(r["pageViewsTotal"])
            continue
        u = r["url"]
        tipo = tipos.get(u) or ("home" if u.rstrip("/") == HOME else "articulo")
        mm = sorted(medios.get(u, []), key=lambda x: -x["v"])
        filas.append({"pos": num(r["posicion"]), "url": u, "titulo": titulo_de_url(u, tipo), "tipo": tipo,
                      "seccion": seccion_de_url(u), "vistas": num(r["pageViewsTotal"]),
                      "dur": num(r["averageDurationPerPage"]), "posts": num(r.get("socialPosts")), "medios": mm})
    return filas, total


def datos_entidad(slug: str, mes: str, previo: str):
    base = "general" if slug == "general" else f"equipos/{slug}"
    pa, pp = MENSUAL / mes / base, MENSUAL / previo / base
    if not (pa / "q01_general.json").exists() and not list(pa.glob("q01*.json")):
        return None
    q01json = next(pa.glob("q01*.json"))
    q01csv = next(pa.glob("q01*.csv"))
    dias = [{"d": r["fecha"][8:10], "pv": num(r["pageViewsTotal"]), "pv_c": num(r["pageViewsTotal_comparada"]),
             "uu": num(r["uniqueUsers"]), "uu_c": num(r["uniqueUsers_comparada"]),
             "du": num(r["averageDurationPerPage"]), "du_c": num(r["averageDurationPerPage_comparada"]),
             "na": num(r["newArticles"]), "na_c": num(r["newArticles_comparada"])}
            for r in leer_csv(q01csv) if re.match(r"\d{4}-\d{2}-\d{2}$", r["fecha"] or "")]
    top_a, tot_a = periodo_top(pa)
    top_p, tot_p = periodo_top(pp)
    fuentes = [{"m": r["medium"], "pv": num(r["pageViewsTotal"]), "pv_c": num(r["pageViewsTotal_comparada"]),
                "uu": num(r["uniqueUsers"]), "uu_c": num(r["uniqueUsers_comparada"])}
               for r in leer_csv(next(pa.glob("q05*.csv"))) if r["posicion"] != "TOTAL_CONSULTA"]
    secciones = [{"s": r["section"], "pv": num(r["pageViewsTotal"]), "pv_c": num(r["pageViewsTotal_comparada"])}
                 for r in leer_csv(pa / "q06_secciones.csv") if r["posicion"] != "TOTAL_CONSULTA"]
    return {"totales": totales_q01(q01json), "dias": dias, "top_actual": top_a, "top_previo": top_p,
            "total_actual": tot_a, "total_previo": tot_p, "fuentes": fuentes, "secciones": secciones}


PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte mensual - El Universal</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{--bg:#f4f6f9;--card:#fff;--ink:#1c2430;--mute:#6b7685;--line:#e3e8ef;--a:#1f6feb;--b:#9aa7b8;--up:#16794c;--down:#b42318;--chip:#eef2f7}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:12px 20px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between}
h1{font-size:18px;margin:0}h1 small{display:block;font-weight:400;color:var(--mute);font-size:12px}
select{font:inherit;padding:7px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;min-width:230px}
main{max-width:1280px;margin:0 auto;padding:16px 20px 60px;display:grid;gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h2{font-size:15px;margin:0 0 12px}.card h2 span{color:var(--mute);font-weight:400;font-size:12px;margin-left:6px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}
.kpi{border:1px solid var(--line);border-radius:10px;padding:14px}
.kpi .n{color:var(--mute);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.kpi .row{display:flex;gap:18px;align-items:flex-end;margin-top:6px;flex-wrap:wrap}
.kpi .v{font-size:26px;font-weight:650}.kpi .p{font-size:16px;color:var(--mute)}.kpi .l{font-size:11px;color:var(--mute)}
.delta{display:inline-block;margin-top:8px;padding:2px 8px;border-radius:99px;font-weight:600;font-size:12px}
.up{background:#e4f4ec;color:var(--up)}.down{background:#fde8e6;color:var(--down)}.flat{background:var(--chip);color:var(--mute)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.chartbox{position:relative;height:270px}
.lists{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.list h3{font-size:13px;margin:0 0 8px;color:var(--mute)}
.item{display:grid;grid-template-columns:28px 1fr auto;gap:10px;padding:8px 6px;border-top:1px solid var(--line);cursor:default;border-radius:6px}
.item:hover{background:#f1f6ff}.pos{color:var(--mute);font-variant-numeric:tabular-nums;text-align:right}
.t{font-weight:550;overflow-wrap:anywhere}.meta{color:var(--mute);font-size:12px;margin-top:2px}
.chip{display:inline-block;background:var(--chip);border-radius:99px;padding:0 7px;font-size:11px;margin-right:6px;color:var(--ink)}
.chip.home{background:#fff4d6}.chip.sec{background:#e8f0ff}
.n2{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.n2 b{display:block}
#tip{position:fixed;z-index:20;pointer-events:none;background:#101828;color:#fff;border-radius:10px;padding:10px 12px;width:260px;box-shadow:0 8px 24px rgba(16,24,40,.25);display:none;font-size:12px}
#tip h4{margin:0 0 6px;font-size:12px;font-weight:600;overflow-wrap:anywhere}
.bar{display:grid;grid-template-columns:86px 1fr 40px;gap:6px;align-items:center;margin:3px 0}
.bar i{display:block;height:7px;background:#5b9dff;border-radius:4px}.bar span:last-child{text-align:right}
#tip .nota{color:#aab4c3;font-size:11px;margin-top:6px}
.secs{width:100%;border-collapse:collapse}.secs td,.secs th{padding:6px 8px;border-top:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}
.secs th{color:var(--mute);font-weight:500;font-size:12px}.secs td:first-child,.secs th:first-child{text-align:left}
.nota{color:var(--mute);font-size:12px;margin-top:8px}
@media(max-width:900px){.two,.lists{grid-template-columns:1fr}}
</style>
</head>
<body>
<header>
  <h1>Reporte mensual - El Universal<small id="sub"></small></h1>
  <label>Equipo: <select id="equipo"></select></label>
</header>
<main>
  <section class="card"><h2>Totales <span id="rango"></span></h2><div class="kpis" id="kpis"></div></section>
  <section class="card"><h2>Día a día <span>mes actual contra mes anterior, mismos días</span></h2>
    <div class="two"><div><div class="nota" style="margin:0 0 6px">Vistas de página</div><div class="chartbox"><canvas id="cPv"></canvas></div></div>
    <div><div class="nota" style="margin:0 0 6px">Usuarios únicos</div><div class="chartbox"><canvas id="cUu"></canvas></div></div></div></section>
  <section class="card"><h2>Top de URL <span>pasa el cursor (o toca) una fila para ver su distribución por fuente de tráfico</span></h2>
    <div class="lists"><div class="list"><h3 id="hA"></h3><div id="lA"></div></div><div class="list"><h3 id="hP"></h3><div id="lP"></div></div></div>
  </section>
  <section class="card"><h2>Fuentes de tráfico <span>vistas de página; los medios se solapan (discover y gnews están dentro de search, etc.): no se suman</span></h2>
    <div class="chartbox" style="height:420px"><canvas id="cFu"></canvas></div></section>
  <section class="card" id="secCard"><h2>Top de secciones <span>vistas de página</span></h2><div id="secs"></div></section>
</main>
<div id="tip"></div>
<script>
const DATOS = __DATOS__;
const META = __META__;
const fmt = n => (n == null ? "-" : Number(n).toLocaleString("es-CO"));
const dur = s => { s = Math.round(s); return Math.floor(s/60) + ":" + String(s%60).padStart(2,"0"); };
const pct = (a,b) => b ? (a-b)/b*100 : null;
const dlt = (a,b) => { const p = pct(a,b); if (p == null) return '<span class="delta flat">sin base</span>';
  return '<span class="delta '+(p>0.05?'up':p<-0.05?'down':'flat')+'">'+(p>0?'+':'')+p.toLocaleString("es-CO",{maximumFractionDigits:1})+' %</span>'; };
let charts = [];
const sel = document.getElementById("equipo");
META.equipos.forEach(e => { if (DATOS[e[0]]) sel.add(new Option(e[1], e[0])); });
document.getElementById("sub").textContent = META.actual + " contra " + META.previo;
document.getElementById("rango").textContent = META.actual + " | " + META.previo;

function kpi(nombre, t, f) {
  f = f || fmt; t = t || {actual:null, previo:null};
  const difv = (t.actual == null || t.previo == null) ? "-" : (f === dur ? (t.actual - t.previo >= 0 ? "+" : "-") + dur(Math.abs(t.actual - t.previo)) : fmt(t.actual - t.previo));
  return '<div class="kpi"><div class="n">'+nombre+'</div><div class="row"><div><div class="v">'+(t.actual == null ? "-" : f(t.actual))+'</div><div class="l">'+META.actual+'</div></div>'
   + '<div><div class="p">'+(t.previo == null ? "-" : f(t.previo))+'</div><div class="l">'+META.previo+'</div></div></div>'
   + dlt(t.actual, t.previo) + ' <span class="l">dif. '+difv+'</span></div>';
}
function linea(id, d, k, kc, f) {
  f = f || fmt;
  return new Chart(document.getElementById(id), {type:"line",
    data:{labels:d.dias.map(x=>x.d), datasets:[
      {label:META.actual, data:d.dias.map(x=>x[k]), borderColor:"#1f6feb", backgroundColor:"#1f6feb", tension:.25, pointRadius:2},
      {label:META.previo, data:d.dias.map(x=>x[kc]), borderColor:"#9aa7b8", backgroundColor:"#9aa7b8", borderDash:[5,4], tension:.25, pointRadius:2}]},
    options:{responsive:true,maintainAspectRatio:false,interaction:{mode:"index",intersect:false},
      plugins:{tooltip:{callbacks:{title:c=>"Día "+c[0].label,label:c=>c.dataset.label+": "+f(c.parsed.y)}}},
      scales:{x:{title:{display:true,text:"Día del mes"}},y:{ticks:{callback:v=>f(v)},beginAtZero:true}}}});
}
function lista(el, filas, total) {
  el.innerHTML = filas.map((f,i) => {
    const chips = (f.tipo==="home"?'<span class="chip home">Home</span>':f.tipo==="seccion"?'<span class="chip sec">Sección</span>':'')
      + (f.seccion && f.tipo==="articulo" ? '<span class="chip">'+f.seccion+'</span>' : '');
    return '<div class="item" data-i="'+i+'"><div class="pos">'+f.pos+'</div><div><div class="t">'+(f.tipo==="home"?"Home":f.titulo)+'</div><div class="meta">'+chips+'<a href="'+f.url+'" target="_blank" rel="noopener" style="color:inherit">abrir</a></div></div>'
      + '<div class="n2"><b>'+fmt(f.vistas)+'</b><span class="meta">'+dur(f.dur)+' | '+fmt(f.posts)+' posteo'+(f.posts===1?'':'s')+' en redes</span></div></div>';
  }).join("");
  el.querySelectorAll(".item").forEach(n => {
    const f = filas[n.dataset.i];
    n.addEventListener("mouseenter", e => mostrar(e, f)); n.addEventListener("mousemove", mover);
    n.addEventListener("mouseleave", ocultar); n.addEventListener("click", e => { if (e.target.tagName !== "A") mostrar(e, f); });
  });
}
const tip = document.getElementById("tip");
function mostrar(e, f) {
  const m = f.medios.slice(0, 8);
  tip.innerHTML = "<h4>"+(f.tipo==="home"?"Home":f.titulo)+"</h4>" + (m.length ? m.map(x =>
    '<div class="bar"><span>'+x.m+'</span><span><i style="width:'+Math.max(2,Math.min(100,x.p))+'%"></i></span><span>'+x.p.toLocaleString("es-CO",{maximumFractionDigits:1})+'%</span></div>').join("")
    + '<div class="nota">% de las vistas de la URL. Los medios se solapan: no suman 100 %.</div>' : "Sin distribución por fuente para esta URL.");
  tip.style.display = "block"; mover(e);
}
function mover(e) { const w = 280, x = e.clientX + 16 + w > innerWidth ? e.clientX - w - 8 : e.clientX + 16;
  tip.style.left = x + "px"; tip.style.top = Math.min(e.clientY + 12, innerHeight - tip.offsetHeight - 10) + "px"; }
function ocultar() { tip.style.display = "none"; }
addEventListener("scroll", ocultar, {passive:true});

function render() {
  const d = DATOS[sel.value];
  charts.forEach(c => c.destroy()); charts = [];
  document.getElementById("kpis").innerHTML = kpi("Vistas de página", d.totales.pageViewsTotal) + kpi("Usuarios únicos", d.totales.uniqueUsers)
    + kpi("Duración media por página (min:seg)", d.totales.averageDurationPerPage, dur) + kpi("Artículos nuevos", d.totales.newArticles);
  charts.push(linea("cPv", d, "pv", "pv_c"), linea("cUu", d, "uu", "uu_c"));
  document.getElementById("hA").textContent = "Top 50 de " + META.actual;
  document.getElementById("hP").textContent = "Top 50 de " + META.previo;
  lista(document.getElementById("lA"), d.top_actual, d.total_actual);
  lista(document.getElementById("lP"), d.top_previo, d.total_previo);
  const fu = d.fuentes.slice(0, 10);
  charts.push(new Chart(document.getElementById("cFu"), {type:"bar",
    data:{labels:fu.map(x=>x.m), datasets:[{label:META.actual,data:fu.map(x=>x.pv),backgroundColor:"#1f6feb"},{label:META.previo,data:fu.map(x=>x.pv_c),backgroundColor:"#b9c3d1"}]},
    options:{indexAxis:"y",responsive:true,maintainAspectRatio:false,plugins:{tooltip:{callbacks:{label:c=>c.dataset.label+": "+fmt(c.parsed.x)}}},scales:{x:{ticks:{callback:v=>fmt(v)}}}}}));
  const sc = document.getElementById("secCard");
  if (d.secciones.length) {
    sc.style.display = "";
    document.getElementById("secs").innerHTML = '<table class="secs"><tr><th>Sección</th><th>'+META.actual+'</th><th>'+META.previo+'</th><th>Variación</th></tr>'
      + d.secciones.slice(0,20).map(s => '<tr><td>'+s.s+'</td><td>'+fmt(s.pv)+'</td><td>'+fmt(s.pv_c)+'</td><td>'+dlt(s.pv, s.pv_c)+'</td></tr>').join("") + '</table>'
      + '<div class="nota">Top 20 por vistas de página del mes actual.</div>';
  } else sc.style.display = "none";
}
sel.addEventListener("change", render); render();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mes", default="2026-11_01-16")
    ap.add_argument("--previo", default="2026-10_01-16")
    a = ap.parse_args()
    datos = {}
    for slug, _ in EQUIPOS:
        d = datos_entidad(slug, a.mes, a.previo)
        if d:
            datos[slug] = d
        else:
            print(f"Aviso: sin datos para {slug}")
    meta = {"actual": etiqueta(a.mes), "previo": etiqueta(a.previo), "equipos": EQUIPOS}
    html = (PLANTILLA.replace("__DATOS__", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
            .replace("__META__", json.dumps(meta, ensure_ascii=False)))
    salida = MENSUAL / a.mes / "reporte_mensual.html"
    salida.write_text(html, encoding="utf-8")
    print(f"Reporte: {salida} ({len(html)//1024} KB, {len(datos)} entidades)")


if __name__ == "__main__":
    main()
