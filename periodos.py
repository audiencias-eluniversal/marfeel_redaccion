"""Periodos de análisis: semanas (lunes a domingo) y meses (día 1 hasta una fecha).

Cada periodo sabe en qué carpeta guarda sus resultados:
  semana -> salida/YYYY-WNN_MM-DD            (año ISO, semana ISO, fecha del lunes)
  mes    -> salida/mensual/YYYY-MM_DD-DD     (año-mes, día inicial y día final)
Dentro de cada una: general/ y equipos/<equipo>/.

Valores por defecto para los análisis automáticos:
  semana: la semana completa anterior a la actual, comparada con la anterior a esa.
  mes:    del día 1 del mes de AYER hasta ayer, comparado con los mismos días del mes anterior
          (si el mes anterior tiene menos días, el rango se recorta a su último día).
"""
import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

SALIDA = Path(__file__).parent / "salida"


@dataclass(frozen=True)
class Periodo:
    tipo: str  # "semana" | "mes"
    inicio: date
    fin: date

    def rango(self) -> dict:
        return {"start": self.inicio.isoformat(), "end": self.fin.isoformat()}

    @property
    def base(self) -> Path:
        if self.tipo == "semana":
            anio, sem, _ = self.inicio.isocalendar()
            return SALIDA / f"{anio}-W{sem:02d}_{self.inicio:%m-%d}"
        return SALIDA / "mensual" / f"{self.inicio:%Y-%m}_{self.inicio:%d}-{self.fin:%d}"

    @property
    def etiqueta(self) -> str:
        return self.base.name


def semana(inicio: date) -> Periodo:
    if inicio.weekday() != 0:
        raise ValueError(f"{inicio} no es lunes")
    return Periodo("semana", inicio, inicio + timedelta(days=6))


def semana_anterior_a(hoy: date) -> Periodo:
    """Última semana completa (lunes a domingo) antes de la semana en la que cae `hoy`."""
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    return semana(lunes_actual - timedelta(days=7))


def semana_previa(p: Periodo) -> Periodo:
    return semana(p.inicio - timedelta(days=7))


def mes(inicio: date, fin: date) -> Periodo:
    if inicio.year != fin.year or inicio.month != fin.month or inicio.day != 1:
        raise ValueError("un mes va del día 1 a un día del mismo mes")
    return Periodo("mes", inicio, fin)


def mes_hasta_ayer(hoy: date) -> Periodo:
    ayer = hoy - timedelta(days=1)
    return mes(ayer.replace(day=1), ayer)


def mes_previo(p: Periodo) -> Periodo:
    """Mismos días del mes anterior (recortado si ese mes es más corto)."""
    fin_mes_prev = p.inicio - timedelta(days=1)
    ini_prev = fin_mes_prev.replace(day=1)
    dias = (p.fin - p.inicio).days + 1
    fin_prev = min(ini_prev + timedelta(days=dias - 1), fin_mes_prev)
    return mes(ini_prev, fin_prev)
