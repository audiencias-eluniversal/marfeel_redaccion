"""Corre el análisis de un periodo (semana o mes) para el general y todos los equipos.

Uso:
  python correr_periodo.py semana [--inicio YYYY-MM-DD]        por defecto: la semana anterior a la actual
  python correr_periodo.py mes [--inicio YYYY-MM-01 --fin YYYY-MM-DD]   por defecto: del día 1 hasta ayer
Opciones: --entidades general,web,...   --forzar (repite pasos ya hechos)   --dry-run (solo muestra el plan)

Para cada entidad (general y cada equipo de config/equipos.json) y periodo P con periodo previo C:
  excl_P / excl_C   lista de URL a excluir (solo equipos con exclusion_urls, p. ej. Web)
  q01, q05          con comparación contra C
  q02_P, q03_P      top 50 de URL y medium de esas URL del periodo P
  q06               secciones con comparación (solo general)
  q02_C, q03_C      top 50 y medium del periodo previo (solo si su CSV aún no existe)
Cada paso se omite si su CSV ya existe. Errores y avisos: salida/errores.log.
"""
import argparse
import csv
import ctypes
import json
import time
import traceback
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import descargar
import medium_por_url
from periodos import (SALIDA, Periodo, mes, mes_hasta_ayer, mes_previo, semana,
                      semana_anterior_a, semana_previa)

CONFIG = Path(__file__).parent / "config"
ERRORES_LOG = SALIDA / "errores.log"
ESPERA_ENFRIAMIENTO = 15 * 60  # tras 3 fallos seguidos por 429 (posible límite de Marfeel)
ESPERA_ENTRE_RONDAS = 5 * 60
# Equipos definidos solo por sección: su q01 debe coincidir con la fila de esa sección del q06 general.
SECCION_DE_EQUIPO = {"deportes": "deportes", "economia": "economica", "mundo": "mundo"}


def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def evitar_suspension():
    """Pide a Windows que no suspenda el equipo mientras corre este proceso."""
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass


def plantilla(nombre: str, P: Periodo, C: Periodo) -> dict:
    """Consulta base de config/<nombre>.json con las fechas del periodo (y el comparado)."""
    q = json.loads((CONFIG / f"{nombre}.json").read_text(encoding="utf-8"))
    q["dates"]["range"] = P.rango()
    if "compare" in q:
        q["compare"] = C.rango()
    return q


@dataclass
class Paso:
    entidad: str
    clave: str
    descripcion: str
    csv: Path
    fn: Callable
    depende: list = field(default_factory=list)
    preview: Callable = None  # devuelve la consulta final (solo para --dry-run)


def construir_pasos(entidad: str, P: Periodo, C: Periodo) -> list:
    eq = None if entidad == "general" else entidad
    sub = descargar.subcarpeta(eq)
    pasos = []

    def add(clave, desc, periodo, nombre_csv, fn, dep=(), preview=None):
        pasos.append(Paso(entidad, clave, desc, periodo.base / sub / f"{nombre_csv}.csv",
                          fn, list(dep), preview))

    dominio = plantilla("q01_general", P, C)
    excl = []
    if eq and "exclusion_urls" in descargar.cargar_equipo(eq):
        for clave, per in (("excl_P", P), ("excl_C", C)):
            add(clave, f"lista de exclusión {per.etiqueta}", per, "urls_excluidas",
                lambda per=per: descargar.generar_exclusiones(
                    eq, dominio, per.inicio.isoformat(), per.fin.isoformat(), per.base))
            excl.append(clave)

    def desc_paso(clave, desc, nombre_plantilla, per, nombre_csv, bases, dep):
        q = plantilla(nombre_plantilla, per, C)
        add(clave, desc, per, nombre_csv,
            lambda q=q: descargar.ejecutar(q, nombre_csv, per.base, eq, bases),
            dep, lambda q=q: descargar.aplicar_equipo(q, eq, bases))

    def medio_paso(clave, desc, per, dep):
        q = plantilla("q02_articulos", per, C)
        add(clave, desc, per, "q03_medium_articulos",
            lambda q=q: medium_por_url.ejecutar(q, "q02_articulos", per.base, eq, [per.base]), dep)

    ambas = [P.base, C.base]
    desc_paso("q01", "q01 general con comparación", "q01_general", P, "q01_general", ambas, excl)
    desc_paso("q02_P", "q02 top 50 URL", "q02_articulos", P, "q02_articulos", [P.base],
              [d for d in excl if d == "excl_P"])
    medio_paso("q03_P", "q03 medium de las URL del top", P,
               ["q02_P"] + [d for d in excl if d == "excl_P"])
    desc_paso("q05", "q05 fuentes de tráfico con comparación", "q05_fuentes_trafico", P,
              "q05_fuentes_trafico", ambas, excl)
    if eq is None:
        desc_paso("q06", "q06 secciones con comparación", "q06_secciones", P, "q06_secciones",
                  ambas, [])
    desc_paso("q02_C", "q02 top 50 URL del periodo previo", "q02_articulos", C, "q02_articulos",
              [C.base], [d for d in excl if d == "excl_C"])
    medio_paso("q03_C", "q03 medium del periodo previo", C,
               ["q02_C"] + [d for d in excl if d == "excl_C"])
    return pasos


def leer_ultima(ruta: Path):
    if not ruta.exists():
        return None
    with open(ruta, encoding="utf-8-sig") as f:
        filas = list(csv.DictReader(f))
    return filas[-1] if filas else None


def leer_filas(ruta: Path) -> list:
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


class Corredor:
    def __init__(self, forzar=False, dry_run=False):
        self.forzar = forzar
        self.dry_run = dry_run
        self.estado = {}  # (fase, entidad, clave) -> {"estado","detalle","hora"}
        self.verificaciones = []  # (fase, entidad, nivel, mensaje)
        self.fallos_429_seguidos = 0
        self.enfriamientos = 0
        self.abortado = False
        self.inicio = ahora()
        SALIDA.mkdir(exist_ok=True)

    # ---------- registro ----------
    def reg(self, k, estado, detalle=""):
        self.estado[k] = {"estado": estado, "detalle": detalle, "hora": ahora()}
        print(f"[{ahora()}] {k[0]} | {k[1]} | {k[2]} -> {estado} {detalle}", flush=True)

    def log_error(self, fase, paso, tipo, status, cuerpo):
        linea = (f"[{ahora()}] fase={fase} entidad={paso.entidad} paso={paso.clave} tipo={tipo} "
                 f"status={status} cuerpo={cuerpo}\n")
        with open(ERRORES_LOG, "a", encoding="utf-8") as f:
            f.write(linea)

    def log_aviso(self, texto):
        with open(ERRORES_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{ahora()}] {texto}\n")
        print(f"[{ahora()}] AVISO: {texto}", flush=True)

    # ---------- ejecución de un paso ----------
    def correr_paso(self, fase, p: Paso):
        k = (fase, p.entidad, p.clave)
        if self.estado.get(k, {}).get("estado") == "OK":
            return  # ya hecho en una ronda anterior
        if p.csv.exists() and not self.forzar:
            self.reg(k, "OMITIDO", "ya existe")
            return
        faltan = [d for d in p.depende
                  if self.estado.get((fase, p.entidad, d), {}).get("estado") not in ("OK", "OMITIDO")]
        if faltan and not self.dry_run:
            self.reg(k, "DEPENDENCIA", f"requiere {', '.join(faltan)}")
            return
        if self.abortado:
            self.reg(k, "NO EJECUTADO", "abortado por límite persistente")
            return
        if self.dry_run:
            self.mostrar_plan(k, p)
            return
        t0 = time.time()
        try:
            p.fn()
        except descargar.ErrorAPI as e:
            self.log_error(fase, p, "ErrorAPI", e.status, e.cuerpo)
            self.reg(k, "FALLÓ", f"HTTP {e.status}: {str(e.cuerpo)[:120]}")
            self.tras_fallo(fase, p, e)
            return
        except Exception as e:  # cualquier otro fallo: se documenta y se sigue
            self.log_error(fase, p, e.__class__.__name__, "-", traceback.format_exc()[-800:].replace("\n", " | "))
            self.reg(k, "FALLÓ", f"{e.__class__.__name__}: {str(e)[:120]}")
            self.fallos_429_seguidos = 0
            return
        self.reg(k, "OK", f"{time.time() - t0:.0f}s")
        self.fallos_429_seguidos = 0
        self.enfriamientos = 0

    def tras_fallo(self, fase, p, e):
        """Detecta un posible límite impuesto por Marfeel: varios pasos seguidos con 429."""
        if e.status == 429:
            self.fallos_429_seguidos += 1
        else:
            self.fallos_429_seguidos = 0
            return
        if self.fallos_429_seguidos >= 3:
            self.enfriamientos += 1
            self.log_aviso(
                f"POSIBLE LÍMITE IMPUESTO POR MARFEEL: {self.fallos_429_seguidos} pasos seguidos "
                f"agotaron los reintentos con 429 (último cuerpo: {e.cuerpo}). Enfriamiento "
                f"{self.enfriamientos}/3 de {ESPERA_ENFRIAMIENTO // 60} min.")
            if self.enfriamientos >= 3:
                self.abortado = True
                self.log_aviso("Se abandonan los pasos restantes: el límite persiste tras 3 enfriamientos.")
                return
            self.fallos_429_seguidos = 0
            time.sleep(ESPERA_ENFRIAMIENTO)

    def mostrar_plan(self, k, p):
        detalle = ""
        if p.preview:
            try:
                q = p.preview()
                partes = []
                for f in q["filters"]:
                    n = len(f["value"])
                    partes.append(f"{f['filter']}:{f['op']}({n})")
                detalle = (f"range {q['dates']['range']['start']}..{q['dates']['range']['end']}"
                           + (f" compare {q['compare']['start']}..{q['compare']['end']}" if q.get("compare") else "")
                           + " filtros " + ", ".join(partes))
            except RuntimeError as e:
                detalle = "(la lista de exclusión aún no existe: se generará antes)"
        print(f"  PLAN {k[0]} | {p.entidad:<16} | {p.clave:<6} | {p.csv.relative_to(SALIDA)} {detalle}", flush=True)

    # ---------- verificaciones ----------
    def verificar(self, fase, entidad, P: Periodo, C: Periodo):
        eq = None if entidad == "general" else entidad
        sub = descargar.subcarpeta(eq)

        def anota(nivel, msg):
            self.verificaciones.append((fase, entidad, nivel, msg))

        q01 = leer_ultima(P.base / sub / "q01_general.csv")
        if not q01:
            anota("ALERTA", "no hay q01: no se puede cuadrar")
            return
        total_p, total_c = float(q01["pageViewsTotal"]), float(q01["pageViewsTotal_comparada"] or 0)
        for clave, per, ref in (("q02", P, total_p), ("q02 previo", C, total_c)):
            t = leer_ultima(per.base / sub / "q02_articulos.csv")
            if not t:
                anota("ALERTA", f"{clave}: falta el CSV")
                continue
            d = float(t["pageViewsTotal"])
            ok = abs(d - ref) <= max(1, ref * 0.001)
            anota("OK" if ok else "ALERTA", f"{clave} TOTAL {d:.0f} vs q01 {ref:.0f}")
        if eq in SECCION_DE_EQUIPO:
            for r in leer_filas(P.base / "general" / "q06_secciones.csv"):
                if r["section"] == SECCION_DE_EQUIPO[eq]:
                    v = float(r["pageViewsTotal"])
                    ok = abs(v - total_p) <= max(1, v * 0.005)
                    anota("OK" if ok else "ALERTA", f"q01 {total_p:.0f} vs q06 general sección {r['section']} {v:.0f}")
        if eq and "exclusion_urls" in descargar.cargar_equipo(eq):
            for per in (P, C):
                n = len(leer_filas(descargar.ruta_exclusiones_base(eq, per.base)))
                lot = [r["url"] for r in leer_filas(per.base / sub / "q02_articulos.csv")
                       if "loter" in r["url"].lower()]
                anota("OK" if not lot else "ALERTA",
                      f"{per.etiqueta}: lista de exclusión {n} URL; URL con 'loter' en el top 50: {len(lot)}")

    # ---------- resumen ----------
    def escribir_resumen(self, ruta: Path, fases: list, extra: str = ""):
        simbolo = {"OK": "OK", "OMITIDO": "omit", "FALLÓ": "FALLÓ", "DEPENDENCIA": "dep", "NO EJECUTADO": "no"}
        out = [f"# Resumen de ejecución", "", f"- Inicio: {self.inicio}", f"- Escrito: {ahora()}"]
        e = descargar.ESTADISTICAS
        out.append(f"- Peticiones a la API: {e['peticiones']} | 429: {e['http_429']} | 5xx: {e['http_5xx']} "
                   f"| errores de red: {e['errores_red']} | tokens renovados: {e['token_renovado']}")
        if self.abortado:
            out.append("- **Se abandonó la ejecución por un posible límite de Marfeel (ver errores.log).**")
        if extra:
            out.append(extra)
        out.append("")
        for fase, P, C in fases:
            out += [f"## {fase}: {P.etiqueta} (previo {C.etiqueta})", ""]
            entidades = sorted({k[1] for k in self.estado if k[0] == fase},
                               key=lambda x: (x != "general", x))
            claves = ["excl_P", "excl_C", "q01", "q02_P", "q03_P", "q05", "q06", "q02_C", "q03_C"]
            out.append("| entidad | " + " | ".join(claves) + " |")
            out.append("|---|" + "---|" * len(claves))
            for ent in entidades:
                fila = []
                for c in claves:
                    est = self.estado.get((fase, ent, c))
                    fila.append(simbolo[est["estado"]] if est else "-")
                out.append(f"| {ent} | " + " | ".join(fila) + " |")
            malos = [(k, v) for k, v in self.estado.items()
                     if k[0] == fase and v["estado"] in ("FALLÓ", "DEPENDENCIA", "NO EJECUTADO")]
            if malos:
                out += ["", "**Pasos con problema:**", ""]
                out += [f"- {k[1]} / {k[2]}: {v['estado']} {v['detalle']}" for k, v in malos]
            ver = [v for v in self.verificaciones if v[0] == fase]
            if ver:
                out += ["", "**Verificaciones:**", ""]
                out += [f"- [{n}] {ent}: {m}" for _, ent, n, m in ver]
            out.append("")
        out += ["Leyenda: OK = descargado ahora; omit = ya existía; FALLÓ = error (ver `salida/errores.log`); "
                "dep = omitido por depender de un paso fallido; no = no ejecutado; - = no aplica.", ""]
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("\n".join(out), encoding="utf-8")


def entidades_por_defecto() -> list:
    equipos = json.loads(descargar.EQUIPOS_JSON.read_text(encoding="utf-8"))
    return ["general"] + list(equipos)


def correr_fase(corredor: Corredor, fase: str, P: Periodo, C: Periodo, entidades=None, rondas=2):
    """Corre todos los pasos del periodo. Reintenta una segunda ronda con lo que haya fallado."""
    entidades = entidades or entidades_por_defecto()
    for ronda in range(1, rondas + 1):
        print(f"\n===== {fase}: ronda {ronda} =====", flush=True)
        for ent in entidades:
            for paso in construir_pasos(ent, P, C):
                corredor.correr_paso(fase, paso)
        if corredor.dry_run:
            return
        malos = [k for k, v in corredor.estado.items()
                 if k[0] == fase and v["estado"] in ("FALLÓ", "DEPENDENCIA", "NO EJECUTADO")]
        if not malos or corredor.abortado or ronda == rondas:
            break
        corredor.log_aviso(f"{fase}: {len(malos)} pasos pendientes; se reintentan tras "
                           f"{ESPERA_ENTRE_RONDAS // 60} min.")
        time.sleep(ESPERA_ENTRE_RONDAS)
    for ent in entidades:
        corredor.verificar(fase, ent, P, C)


def main():
    ap = argparse.ArgumentParser(description="Análisis de un periodo para general y equipos")
    ap.add_argument("tipo", choices=["semana", "mes"])
    ap.add_argument("--inicio")
    ap.add_argument("--fin")
    ap.add_argument("--entidades")
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    hoy = date.today()
    if a.tipo == "semana":
        P = semana(date.fromisoformat(a.inicio)) if a.inicio else semana_anterior_a(hoy)
        C = semana_previa(P)
    else:
        P = (mes(date.fromisoformat(a.inicio), date.fromisoformat(a.fin)) if a.inicio
             else mes_hasta_ayer(hoy))
        C = mes_previo(P)
    evitar_suspension()
    corredor = Corredor(forzar=a.forzar, dry_run=a.dry_run)
    fase = f"{a.tipo} {P.etiqueta}"
    entidades = a.entidades.split(",") if a.entidades else None
    correr_fase(corredor, fase, P, C, entidades)
    if not a.dry_run:
        ruta = SALIDA / "resumenes" / f"{datetime.now():%Y%m%d_%H%M}_{a.tipo}.md"
        corredor.escribir_resumen(ruta, [(fase, P, C)])
        print("Resumen:", ruta)


if __name__ == "__main__":
    main()
