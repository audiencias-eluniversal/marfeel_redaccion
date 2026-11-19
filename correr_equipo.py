"""Corre el análisis completo (sin secciones) de un equipo de trabajo.

Uso:  python correr_equipo.py entretenimiento [--forzar]

Pasos (cada uno respeta el límite de 1 petición/minuto de Marfeel; ~8 min en total):
  1. q01_general                          semana de interés, con comparación
  2. q02_articulos                        top 50 URL, semana de interés
  3. q03_medium (de q02_articulos)        medium de esas URL
  4. q02_articulos_semana_anterior        top 50 URL, semana previa
  5. q03_medium (de la semana anterior)   medium de esas URL
  6. q05_fuentes_trafico                  global por medium, con comparación
No incluye q06 (secciones). Si se interrumpe, al relanzarlo se saltan los pasos cuyo
CSV ya existe (--forzar los repite).
"""
import json
import sys
from pathlib import Path

import descargar
import medium_por_url

CONFIG = Path(__file__).parent / "config"

PASOS = [
    ("descargar", "q01_general", "q01_general"),
    ("descargar", "q02_articulos", "q02_articulos"),
    ("medium", "q02_articulos", "q03_medium_articulos"),
    ("descargar", "q02_articulos_semana_anterior", "q02_articulos_semana_anterior"),
    ("medium", "q02_articulos_semana_anterior", "q03_medium_articulos_semana_anterior"),
    ("descargar", "q05_fuentes_trafico", "q05_fuentes_trafico"),
]


def csv_de_salida(config: str, salida: str, equipo: str) -> Path:
    q = json.loads((CONFIG / f"{config}.json").read_text(encoding="utf-8"))
    carpeta = descargar.carpeta_salida(
        q["dates"]["range"]["start"], descargar.subcarpeta(equipo)
    )
    return carpeta / f"{salida}.csv"


def asegurar_exclusiones(equipo: str):
    """Si el equipo define exclusion_urls, genera la lista de cada periodo (semana de
    interés y comparada) que aún no exista."""
    if "exclusion_urls" not in descargar.cargar_equipo(equipo):
        return
    base = json.loads((CONFIG / "q01_general.json").read_text(encoding="utf-8"))
    periodos = [base["dates"]["range"]] + ([base["compare"]] if base.get("compare") else [])
    for p in periodos:
        if not descargar.ruta_exclusiones(equipo, p["start"]).exists():
            print(f"[0] Lista de exclusión {p['start']} a {p['end']}", flush=True)
            descargar.generar_exclusiones(equipo, base, p["start"], p["end"])
        else:
            print(f"[0] Lista de exclusión {p['start']}: ya existe", flush=True)


def main(equipo: str, forzar: bool = False):
    descargar.cargar_equipo(equipo)  # falla pronto si el equipo no existe
    asegurar_exclusiones(equipo)
    for n, (tipo, config, salida) in enumerate(PASOS, start=1):
        destino = csv_de_salida(config, salida, equipo)
        if destino.exists() and not forzar:
            print(f"[{n}/{len(PASOS)}] {salida}: ya existe, se omite", flush=True)
            continue
        print(f"[{n}/{len(PASOS)}] {salida} ({tipo})", flush=True)
        ruta = str(CONFIG / f"{config}.json")
        if tipo == "descargar":
            descargar.main(ruta, equipo=equipo)
        else:
            medium_por_url.main(ruta, equipo=equipo)
    print("TERMINADO", equipo, flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--forzar"]
    if len(args) != 1:
        sys.exit(__doc__)
    main(args[0], forzar="--forzar" in sys.argv)
