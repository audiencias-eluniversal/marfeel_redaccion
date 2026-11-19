"""Cliente mínimo de la API de Marfeel (api.newsroom.bi): autenticación, consulta con límite de
1 petición/minuto, paginación y conversión de la respuesta a filas.

Credenciales (en este orden):
  1. variables de entorno MARFEEL_EMAIL y MARFEEL_PASSWORD
  2. archivo credenciales.md junto a este script (ver credenciales.ejemplo.md)
Nunca escribas las credenciales en el chat ni en otros archivos.
"""
import json
import os
import re
import time
from pathlib import Path

import sys

import requests

# La consola de Windows (cp1252) no imprime ≥, ⊂, tildes raras: forzar UTF-8 para que no falle al escribir.
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).parent
CREDENCIALES_MD = BASE_DIR / "credenciales.md"
TOKEN_FILE = BASE_DIR / "token.json"
SIGNIN_URL = "https://api.newsroom.bi/api/user/signin"
QUERY_URL = "https://api.newsroom.bi/api/dashboard/query"
DOMINIO = "www.eluniversal.com.co"
ESPERA = 65          # Marfeel: 1 petición por minuto por cuenta (compartido por todos los usuarios de la cuenta)
LIMITE_FILAS = 500   # máximo de filas por respuesta
_ultima = 0.0


class ErrorAPI(Exception):
    def __init__(self, status, cuerpo):
        super().__init__(f"HTTP {status}: {cuerpo}")
        self.status, self.cuerpo = status, cuerpo


def _credenciales():
    correo, clave = os.environ.get("MARFEEL_EMAIL"), os.environ.get("MARFEEL_PASSWORD")
    if correo and clave:
        return correo, clave
    if not CREDENCIALES_MD.exists():
        raise SystemExit("Faltan credenciales: crea credenciales.md (ver credenciales.ejemplo.md) "
                         "o define MARFEEL_EMAIL y MARFEEL_PASSWORD.")
    t = CREDENCIALES_MD.read_text(encoding="utf-8")
    c, p = re.search(r"\*\*Correo:\*\*\s*`([^`]+)`", t), re.search(r"\*\*Contraseña:\*\*\s*`([^`]+)`", t)
    if not c or not p:
        raise SystemExit("No pude leer correo/contraseña de credenciales.md (formato en credenciales.ejemplo.md).")
    return c.group(1), p.group(1)


def _buscar_token(data):
    if isinstance(data, dict):
        for k in ("token", "accessToken", "access_token", "jwt", "idToken"):
            if isinstance(data.get(k), str):
                return data[k]
        for v in data.values():
            t = _buscar_token(v)
            if t:
                return t
    return None


def token(forzar=False):
    """Token guardado (válido 14 días) o uno nuevo si no existe o forzar=True."""
    if not forzar and TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))["token"]
        except (ValueError, KeyError):
            pass
    correo, clave = _credenciales()
    r = requests.post(SIGNIN_URL, json={"email": correo, "password": clave}, timeout=30)
    r.raise_for_status()
    t = _buscar_token(r.json())
    if not t:
        raise RuntimeError("El signin no devolvió token.")
    TOKEN_FILE.write_text(json.dumps({"token": t}), encoding="utf-8")
    return t


def consultar(query):
    """POST de una consulta. Espera para respetar 1/minuto, renueva el token si lo rechazan (401/403)
    y reintenta 429, 5xx y errores de red (hasta 6 veces). Un 400 u otro error lanza ErrorAPI."""
    global _ultima
    renovado, ult = False, (None, "")
    for _ in range(6):
        falta = ESPERA - (time.time() - _ultima)
        if _ultima and falta > 0:
            print(f"  espera {falta:.0f}s (límite de la API: 1 petición por minuto)...", flush=True)
            time.sleep(falta)
        _ultima = time.time()
        try:
            r = requests.post(QUERY_URL, json=query, timeout=120,
                              headers={"Authorization": f"Bearer {token(forzar=renovado)}"})
        except requests.RequestException as e:
            ult = ("red", repr(e)[:300])
            time.sleep(ESPERA)
            continue
        if r.status_code in (401, 403) and not renovado:
            renovado = True
            continue
        if r.status_code == 429 or r.status_code >= 500:
            ult = (r.status_code, r.text[:500])
            time.sleep(ESPERA)
            continue
        if r.status_code >= 400:
            raise ErrorAPI(r.status_code, r.text[:500])
        return r.json()
    raise ErrorAPI(*ult)


def consultar_todo(query):
    """Como consultar() pero pagina con limit=500/from hasta traer todas las filas."""
    q = dict(query, limit=LIMITE_FILAS, **{"from": 0})
    union = None
    while True:
        resp = consultar(q)
        n = max(len(f["values"]) for m in resp for f in (m["actualData"], m.get("compareData")) if f)
        if union is None:
            union = resp
        else:
            for dest, nuevo in zip(union, resp):
                for campo in ("actualData", "compareData"):
                    if dest.get(campo) and nuevo.get(campo):
                        vistos = {v["key"] for v in dest[campo]["values"]}
                        dest[campo]["values"] += [v for v in nuevo[campo]["values"] if v["key"] not in vistos]
        if n < LIMITE_FILAS:
            return union
        q["from"] += LIMITE_FILAS


def a_filas_agrupado(resp, group_by):
    """Una fila por elemento del groupBy (los elementos se unen entre métricas por 'key').
    Si la consulta lleva `compare`, cada métrica añade la columna <métrica>_comparada (vacía si el
    elemento no aparece en el periodo comparado). Última fila: TOTAL_CONSULTA (total de toda la
    consulta, no solo de lo devuelto)."""
    metricas = [m["metric"] for m in resp]
    comp = any(m.get("compareData") for m in resp)
    elementos = {}
    actual, comparado = {n: {} for n in metricas}, {n: {} for n in metricas}
    for m in resp:
        for fuente, destino in ((m["actualData"], actual), (m.get("compareData"), comparado)):
            if not fuente:
                continue
            for v in fuente["values"]:
                elementos.setdefault(v["key"], [i["value"] for i in v["items"]])
                destino[m["metric"]][v["key"]] = v["total"]
    cab = ["posicion"] + list(group_by)
    for n in metricas:
        cab += [n] + ([f"{n}_comparada"] if comp else [])
    filas = []
    for pos, (k, dims) in enumerate(elementos.items(), 1):
        fila = [pos] + (dims + [""] * len(group_by))[:len(group_by)]
        for n in metricas:
            fila += [actual[n].get(k, "")] + ([comparado[n].get(k, "")] if comp else [])
        filas.append(fila)
    tot = ["TOTAL_CONSULTA"] + [""] * len(group_by)
    for x in resp:
        tot += [x["actualData"]["total"]] + ([(x.get("compareData") or {}).get("total", "")] if comp else [])
    filas.append(tot)
    return cab, filas


def a_filas(resp):
    """Consulta SIN groupBy: una fila por día (fecha, fecha_comparada y cada métrica con su _comparada)
    + fila TOTAL. Para promedios (averageDurationPerPage) el total es un promedio, no una suma."""
    metricas = [x["metric"] for x in resp]
    actual, comparado, f_act, f_cmp = {}, {}, [], []
    for x in resp:
        for fuente, destino, fechas in ((x["actualData"], actual, f_act), (x.get("compareData"), comparado, f_cmp)):
            if not fuente:
                continue
            serie = [(p["label"], p[next(k for k in p if k != "label")]) for p in fuente["data"]]
            destino[x["metric"]] = [v for _, v in serie]
            if len(fechas) < len(serie):
                fechas[:] = [l for l, _ in serie]
    cab = ["fecha", "fecha_comparada"]
    for n in metricas:
        cab += [n, f"{n}_comparada"]
    filas = []
    for i, f in enumerate(f_act):
        fila = [f[:10], f_cmp[i][:10] if i < len(f_cmp) else ""]
        for n in metricas:
            fila += [actual[n][i] if i < len(actual.get(n, [])) else "",
                     comparado[n][i] if i < len(comparado.get(n, [])) else ""]
        filas.append(fila)
    tot = ["TOTAL", ""]
    for x in resp:
        tot += [x["actualData"]["total"], (x.get("compareData") or {}).get("total", "")]
    filas.append(tot)
    return cab, filas


def periodistas():
    """{código: id de Marfeel (Value)} desde periodistas.txt (columnas Periodista;Código;Grupo;Value)."""
    ruta = BASE_DIR / "periodistas.txt"
    if not ruta.exists():
        return {}
    out = {}
    for linea in ruta.read_text(encoding="utf-8-sig").splitlines()[1:]:
        p = [x.strip() for x in linea.split(";")]
        if len(p) >= 4 and p[3].isdigit():
            out[p[1]] = int(p[3])
    return out
