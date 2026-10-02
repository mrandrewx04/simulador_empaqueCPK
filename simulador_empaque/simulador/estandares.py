"""Lectura del archivo de estándares de acondicionamiento (und/h con 3 personas)
y proyección de cada producto a las distribuciones con banda.

Método:
1. Para cada familia se simula la mesa manual (A) y las distribuciones B, C, D
   en una rejilla de escalas de tiempo (productos más rápidos o más lentos que
   la referencia).
2. Para cada producto se busca la escala con la que la mesa manual reproduce su
   estándar real, y se interpola la producción de cada distribución a esa escala.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .familias import FAMILIAS, FORMA_A_FAMILIA, LAYOUTS, Parametros
from .motor import simular

COL_COD, COL_PROD, COL_CLI, COL_STD, COL_FORMA, COL_ENV = (
    "Cod ARTICULO", "PRODUCTO", "Cliente", "ESTANDAR", "FORMA", "NUMERO DE ENVASES POR PLEGADIZA")
COLS_EXTRA = ["NUMERO DE ETIQUETAS", "TERMO- ENCOGIDO", "ENSOBRAR", "CON APLICADOR", "STIKER",
              "CON COPA/ CUCHARA", "CON INSERTO", "PVC   BLANCO"]


def _inferir_forma(forma, producto: str):
    if isinstance(forma, str) and forma.strip():
        f = forma.strip().upper()
        return ("LIQ" if f in ("JBE", "FRASCO") else f), f in ("JBE", "FRASCO")
    p = str(producto).upper()
    if "JARABE" in p or "JBE" in p:
        return "LIQ", True
    if "PPS" in p or "SACHET" in p:
        return "POL", True
    if "TABLETA" in p:
        return "TAB", True
    return "SIN", True


def leer_estandares(ruta: str | Path) -> pd.DataFrame:
    """Lee la hoja 'STD ACOND' y agrega columnas normalizadas."""
    df = pd.read_excel(ruta, sheet_name=0, dtype={COL_COD: str})
    df["estandar"] = pd.to_numeric(df[COL_STD], errors="coerce")
    inf = [_inferir_forma(f, p) for f, p in zip(df[COL_FORMA], df[COL_PROD])]
    df["forma_aj"] = [x[0] for x in inf]
    df["forma_inferida"] = ["Sí" if x[1] else "No" for x in inf]
    df["familia"] = df["forma_aj"].map(FORMA_A_FAMILIA)
    extras = [c for c in COLS_EXTRA if c in df.columns]
    df["ops_adicionales"] = df[extras].notna().sum(axis=1)
    return df


def rejilla_familia(familia: str, base: Parametros, escalas, reps=2, progreso=None) -> pd.DataFrame:
    """Simula A-D a varias escalas de tiempo. Devuelve und/h efectiva por escala y layout."""
    filas = []
    for s in escalas:
        fila = {"escala": s}
        for L in LAYOUTS:
            r = simular(base.copia(familia=familia, layout=L, escala_tiempos=s), reps)
            fila[L] = r["por_hora_efectiva"]
        filas.append(fila)
        if progreso:
            progreso(familia, s)
    return pd.DataFrame(filas)


def _interp_log(x, xs, ys):
    """Interpolación lineal en escala log-log (xs creciente)."""
    lx, lxs, lys = math.log(x), np.log(xs), np.log(ys)
    return float(np.exp(np.interp(lx, lxs, lys)))


def proyectar_productos(df: pd.DataFrame, base: Parametros | None = None, n_escalas=14,
                        reps=2, progreso=None) -> tuple[pd.DataFrame, dict]:
    """Agrega a cada producto la producción estimada con cada distribución."""
    base = base or Parametros(operarios=3)
    escalas = np.geomspace(0.15, 25, n_escalas)
    rejillas = {}
    for fam in FAMILIAS:
        if (df["familia"] == fam).any():
            rejillas[fam] = rejilla_familia(fam, base, escalas, reps, progreso)
    horas = base.efectivo_seg / 3600
    res = []
    for _, r in df.iterrows():
        std, fam = r["estandar"], r["familia"]
        fila = {}
        if pd.notna(std) and std > 0 and fam in rejillas:
            g = rejillas[fam]
            # A es decreciente con la escala: invertimos (A creciente al revés)
            a_vals = g["A"].values[::-1]
            esc = g["escala"].values[::-1]
            s = _interp_log(std, a_vals, esc)
            fila["escala_tiempos"] = s
            ref = _interp_log(s, g["escala"].values, g["A"].values)
            for L in LAYOUTS:
                ratio = _interp_log(s, g["escala"].values, g[L].values) / ref
                fila[f"und_h_{L}"] = std * ratio
                fila[f"und_turno_{L}"] = std * ratio * horas
            mejor = max("BCD", key=lambda L: fila[f"und_h_{L}"])
            fila["mejor_layout"] = mejor
            fila["ganancia_mejor"] = fila[f"und_h_{mejor}"] / std - 1
            fila["ciclo_linea_s"] = 3600 / std
            fila["contenido_trabajo_s"] = 3600 / std * base.operarios
        res.append(fila)
    out = pd.concat([df.reset_index(drop=True), pd.DataFrame(res)], axis=1)
    return out, rejillas
