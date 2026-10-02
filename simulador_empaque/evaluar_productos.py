"""Proyecta cada producto del archivo de estándares a las distribuciones con banda.

El estándar (und/h con 3 personas en mesa manual) calibra los tiempos de cada
producto; luego se estima cuánto produciría con B, C y D.

    python evaluar_productos.py
    python evaluar_productos.py --archivo "datos/tiempos_acond.xlsx" --operarios-banda 3
"""
import argparse
import time
from pathlib import Path

import pandas as pd

from simulador import Parametros
from simulador.estandares import leer_estandares, proyectar_productos

AQUI = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archivo", default=str(AQUI / "datos" / "tiempos_acond.xlsx"))
    ap.add_argument("--salida", default=str(AQUI / "salidas" / "proyeccion_productos.xlsx"))
    ap.add_argument("--operarios-banda", type=int, default=3, help="operarios en la línea (el estándar es con 3)")
    ap.add_argument("--reps", type=int, default=2)
    a = ap.parse_args()

    t0 = time.time()
    df = leer_estandares(a.archivo)
    print(f"{len(df)} productos leídos · {df['estandar'].notna().sum()} con estándar numérico")
    base = Parametros(operarios=a.operarios_banda)
    out, rejillas = proyectar_productos(df, base, reps=a.reps,
                                        progreso=lambda f, s: print(f"  simulando {f:12s} escala {s:5.2f}", end="\r"))
    print()

    cols = ["Cod ARTICULO", "PRODUCTO", "Cliente", "forma_aj", "familia", "ops_adicionales", "estandar",
            "ciclo_linea_s", "contenido_trabajo_s", "und_h_A", "und_h_B", "und_h_C", "und_h_D",
            "und_turno_A", "und_turno_C", "und_turno_D", "mejor_layout", "ganancia_mejor"]
    nombres = {"forma_aj": "Forma", "familia": "Familia", "ops_adicionales": "Operaciones adicionales",
               "estandar": "Estándar und/h (3 op)", "ciclo_linea_s": "Ciclo línea (s/und)",
               "contenido_trabajo_s": "Contenido trabajo (s-hombre/und)",
               "und_h_A": "Und/h A manual", "und_h_B": "Und/h B lineal", "und_h_C": "Und/h C ambos lados",
               "und_h_D": "Und/h D U+flotante", "und_turno_A": "Und/turno A", "und_turno_C": "Und/turno C",
               "und_turno_D": "Und/turno D", "mejor_layout": "Mejor distribución", "ganancia_mejor": "Ganancia vs manual"}
    tabla = out[cols].rename(columns=nombres)
    resumen = (out.dropna(subset=["mejor_layout"])
               .groupby("forma_aj")
               .agg(Productos=("estandar", "size"), Estandar_prom=("estandar", "mean"),
                    Und_h_C=("und_h_C", "mean"), Und_h_D=("und_h_D", "mean"),
                    Ganancia_mejor_prom=("ganancia_mejor", "mean"),
                    Mejor_mas_frecuente=("mejor_layout", lambda s: s.mode().iat[0]))
               .round(2).reset_index().rename(columns={"forma_aj": "Forma"}))
    Path(a.salida).parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(a.salida) as xw:
        tabla.to_excel(xw, sheet_name="Productos", index=False)
        resumen.to_excel(xw, sheet_name="Resumen por forma", index=False)
        for fam, g in rejillas.items():
            g.round(1).to_excel(xw, sheet_name=f"Rejilla {fam}", index=False)
    print(resumen.to_string(index=False))
    print(f"\nGuardado en {a.salida}  ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
