"""Exporta la presentación (project/deck.json + slides + deck.css) a UN solo HTML autocontenido
(imágenes incrustadas en base64, sin notas del orador) para publicarlo, p. ej., en GitHub Pages.

Uso: python exportar_html.py <carpeta_deck> <carpeta_imagenes> <salida.html> [ruta_logo_EU, por defecto ../eu_rojo.svg]
  carpeta_deck     = la que contiene project/ (deck.json, deck.css, slides/)
  carpeta_imagenes = _assets_deck (nombres de archivo del mapa BLOB)
Navegación: flechas, clic a derecha/izquierda, o #N en la URL."""
import base64
import json
import re
import sys
from pathlib import Path

BLOB = {  # id del artefacto -> archivo
    "ba1b0031461da60fb4da3c02f0ab0826": "logo_camara.webp",
    "2904a995b65099ee34f1c722962c6111": "pagina_impresa.jpg",
    "c5aa4a58bddf422d5caebfcd8945b168": "foto_cinta.jpg",
    "f990e3fdc75cfd5d806cb5c10f79fdef": "foto_feria.jpg",
    "4277810d5d720be4fc4a52195e17a399": "foto_baile.jpg",
    "496d59209c1cbe568a41e69d6d684f46": "foto_discurso.jpg",
    "7c4d035efff0a2bec465e06ffcdad86c": "foto_revista.jpg",
    # Logo de El Universal: NO se incrusta; se enlaza al eu_rojo.svg de la raíz del repositorio
    # (ruta relativa, 4.º argumento), para que todos los informes usen el mismo archivo.
    "ad07436b88a560af55af44190155e7f3": "@LOGO_EU",
}
MIME = {".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

BASE = """*{margin:0}
html,body{height:100%;background:#14161A;overflow:hidden;font:32px/1.2 'Inter',Arial,sans-serif}
h1{font-size:96px;font-weight:600}h2{font-size:64px;font-weight:600}h3{font-size:44px;font-weight:600}
p,li,h1,h2,h3,td,th{overflow-wrap:break-word;text-wrap:pretty}
table{width:100%;border-collapse:separate;border-spacing:0;border:solid #0003;border-width:2px 0 0 2px}
th,td{padding:.35em .6em;text-align:left;border:solid #0003;border-width:0 2px 2px 0}
#stage{position:absolute;left:0;top:0;width:1920px;height:1080px;transform-origin:0 0}
#stage>section{position:absolute;left:0;top:0;width:1920px;height:1080px;overflow:hidden;display:none;box-sizing:border-box}
#stage>section.on{display:flex}
#n{position:fixed;right:14px;bottom:10px;font:14px Arial,sans-serif;color:#fff8;pointer-events:none}
"""

JS = """
const S=[...document.querySelectorAll('#stage>section')];let i=0;
function fit(){const k=Math.min(innerWidth/1920,innerHeight/1080);const st=document.getElementById('stage');
st.style.transform='translate('+((innerWidth-1920*k)/2)+'px,'+((innerHeight-1080*k)/2)+'px) scale('+k+')'}
function go(n){i=Math.max(0,Math.min(S.length-1,n));S.forEach((s,j)=>s.classList.toggle('on',j===i));
document.getElementById('n').textContent=(i+1)+' / '+S.length;history.replaceState(null,'','#'+(i+1))}
addEventListener('resize',fit);
addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key))go(i+1);if(['ArrowLeft','PageUp'].includes(e.key))go(i-1);if(e.key==='Home')go(0);if(e.key==='End')go(S.length-1)});
addEventListener('click',e=>go(e.clientX>innerWidth/2?i+1:i-1));
fit();go((parseInt(location.hash.slice(1))||1)-1);
"""


def main():
    deck_dir, img_dir, salida = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    logo_eu = sys.argv[4] if len(sys.argv) > 4 else "../eu_rojo.svg"
    deck = json.loads((deck_dir / "project/deck.json").read_text(encoding="utf-8"))
    css = (deck_dir / "project/deck.css").read_text(encoding="utf-8")
    secciones = []
    for sid in deck["order"]:
        h = (deck_dir / f"project/slides/{sid}.html").read_text(encoding="utf-8")
        h = re.sub(r"<aside>.*?</aside>", "", h, flags=re.S)
        for k, f in BLOB.items():
            if f == "@LOGO_EU":
                h = h.replace(f"/_blob/{k}", logo_eu)
                continue
            p = img_dir / f
            data = base64.b64encode(p.read_bytes()).decode()
            h = h.replace(f"/_blob/{k}", f"data:{MIME[p.suffix.lower()]};base64,{data}")
        if "/_blob/" in h:
            raise SystemExit(f"Imagen sin mapear en {sid}")
        secciones.append(h)
    fuentes = deck["faces"]["inter"]["href"]
    titulo = deck["title"]
    html = (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex,nofollow"><title>{titulo}</title>'
            f'<link rel="stylesheet" href="{fuentes}"><style>{BASE}</style><style>{css}</style></head><body>'
            f'<div id="stage">{"".join(secciones)}</div><div id="n"></div><script>{JS}</script></body></html>')
    salida.write_text(html, encoding="utf-8")
    print(f"{salida} {salida.stat().st_size/1024/1024:.1f} MB, {len(secciones)} diapositivas")


if __name__ == "__main__":
    main()
