"""Histórico de una sola vez: semana W46, pausa, y análisis mensual (1 a 16 de noviembre contra
1 a 16 de octubre). Para el general y todos los equipos. Al final deja el resumen, anota la
ejecución en CONTEXTO.md y apaga el equipo (aunque haya habido errores).

Uso:  python historico_noche.py [--dry-run] [--no-apagar]
Salidas: salida/resumen_ejecucion.md, salida/errores.log y los CSV de cada periodo.
Un Ctrl+C detiene el proceso SIN apagar el equipo.
"""
import argparse
import subprocess
import time
import traceback
from datetime import date, datetime

import correr_periodo as cp
from periodos import SALIDA, mes, semana

PAUSA_ENTRE_FASES = 5 * 60
RESUMEN = SALIDA / "resumen_ejecucion.md"
CONTEXTO = cp.Path(__file__).parent / "CONTEXTO.md"

FASES = [
    ("W46", semana(date(2026, 11, 9)), semana(date(2026, 11, 2))),
    ("Mensual 1-16 nov", mes(date(2026, 11, 1), date(2026, 11, 16)),
     mes(date(2026, 10, 1), date(2026, 10, 16))),
]


def anotar_en_contexto(corredor: cp.Corredor, apagado: bool, interrumpido: bool):
    """Añade una línea al final de CONTEXTO.md (sección 9) con el resultado de la ejecución."""
    conteo = {}
    for v in corredor.estado.values():
        conteo[v["estado"]] = conteo.get(v["estado"], 0) + 1
    e = cp.descargar.ESTADISTICAS
    alertas = sum(1 for v in corredor.verificaciones if v[2] == "ALERTA")
    linea = (f"- {datetime.now():%Y-%m-%d %H:%M}: histórico W46 + mensual 1-16 nov (vs 1-16 oct). "
             f"Pasos: {conteo}. Peticiones: {e['peticiones']} (429: {e['http_429']}). "
             f"Verificaciones con ALERTA: {alertas}. "
             f"{'Abandonado por posible límite de Marfeel. ' if corredor.abortado else ''}"
             f"{'Interrumpido a mano. ' if interrumpido else ''}"
             f"{'Equipo apagado al terminar. ' if apagado else ''}"
             f"Detalle en salida/resumen_ejecucion.md y salida/errores.log.\n")
    texto = CONTEXTO.read_text(encoding="utf-8")
    if "## 9. Ejecuciones automáticas" not in texto:
        texto = texto.rstrip("\n") + "\n\n## 9. Ejecuciones automáticas\n\n"
    CONTEXTO.write_text(texto.rstrip("\n") + "\n" + linea, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-apagar", action="store_true")
    a = ap.parse_args()

    cp.evitar_suspension()
    corredor = cp.Corredor(dry_run=a.dry_run)
    interrumpido = False
    try:
        for i, (nombre, P, C) in enumerate(FASES):
            if i and not a.dry_run:
                corredor.log_aviso(f"Pausa de {PAUSA_ENTRE_FASES // 60} min antes de la fase {nombre}.")
                time.sleep(PAUSA_ENTRE_FASES)
            cp.correr_fase(corredor, nombre, P, C)
            if not a.dry_run:
                corredor.escribir_resumen(RESUMEN, FASES)  # resumen parcial por si algo se corta
    except KeyboardInterrupt:
        interrumpido = True
        corredor.log_aviso("Interrumpido a mano (Ctrl+C): no se apaga el equipo.")
    except Exception:
        corredor.log_aviso("ERROR INESPERADO en el orquestador: " + traceback.format_exc()[-1500:].replace("\n", " | "))
    finally:
        if a.dry_run:
            return
        apagar = not a.no_apagar and not interrumpido
        corredor.escribir_resumen(
            RESUMEN, FASES,
            extra=("- El equipo se apaga al terminar (`shutdown /a` lo cancela durante 60 s)." if apagar else ""))
        try:
            anotar_en_contexto(corredor, apagar, interrumpido)
        except Exception:
            corredor.log_aviso("No se pudo anotar en CONTEXTO.md: " + traceback.format_exc()[-400:].replace("\n", " | "))
        print(f"[{cp.ahora()}] Resumen en {RESUMEN}", flush=True)
        if apagar:
            print(f"[{cp.ahora()}] Apagando el equipo en 60 s...", flush=True)
            subprocess.run(["shutdown", "/s", "/t", "60", "/c",
                            "Fin del historico Marfeel. Para cancelar: shutdown /a"])


if __name__ == "__main__":
    main()
