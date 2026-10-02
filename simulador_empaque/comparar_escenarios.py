"""Compara las 4 distribuciones para una familia y número de operarios.

Ejemplos:
    python comparar_escenarios.py
    python comparar_escenarios.py --familia liquidos --operarios 3 --meta 3000
    python comparar_escenarios.py --produccion-real 2500   # calibra la mesa manual
    python comparar_escenarios.py --todo                    # todas las familias x 3 y 4 operarios
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from simulador import FAMILIAS, LAYOUTS, Parametros, comparar, calibrar_factor_manual, simular
from simulador.graficos import grafico_balanceo, grafico_comparacion, grafico_sensibilidad, grafico_utilizacion

SALIDAS = Path(__file__).parent / "salidas"


def tabla(res: dict, p: Parametros) -> pd.DataFrame:
    base = res["A"]["buenas"]
    filas = []
    for k, r in res.items():
        filas.append({
            "Familia": FAMILIAS[p.familia]["nombre"], "Operarios": p.operarios, "Distribución": LAYOUTS[k]["nombre"],
            "Und/turno": round(r["buenas"]), "Und/h": round(r["por_hora"]),
            "Und/operario·h": round(r["por_operario_hora"], 1),
            "Cambio vs manual": r["buenas"] / base - 1, "OEE": r["oee"],
            "Eficiencia balanceo": r["eficiencia_balance"], "WIP medio": round(r["wip_prom"], 1),
            "Cuello (s/und)": round(r["cuello_seg"], 2),
            "Estaciones": " | ".join(f"{e.ops} op: {' + '.join(e.nombres)}" for e in r["estaciones"])
                          + (" | + flotante" if r["flex"] else ""),
        })
    return pd.DataFrame(filas)


def un_escenario(p: Parametros, reps: int, meta: float | None):
    res = comparar(p, reps)
    df = tabla(res, p)
    print(df.drop(columns=["Estaciones"]).to_string(index=False, formatters={
        "Cambio vs manual": "{:+.0%}".format, "OEE": "{:.0%}".format, "Eficiencia balanceo": "{:.0%}".format}))
    mejor = max(res, key=lambda k: res[k]["buenas"])
    print(f"\nRecomendado: {LAYOUTS[mejor]['nombre']}")
    for e in res[mejor]["estaciones"]:
        print(f"  {e.ops} op · {e.carga:.1f} s · {' → '.join(e.nombres)}")

    # gráficas
    SALIDAS.mkdir(exist_ok=True)
    pref = SALIDAS / f"{p.familia}_{p.operarios}op"
    fig, ax = plt.subplots(figsize=(9, 3.8)); grafico_comparacion(res, meta, ax); fig.tight_layout(); fig.savefig(f"{pref}_comparacion.png", dpi=150)
    takt = p.efectivo_seg / meta if meta else None
    fig, ax = plt.subplots(figsize=(6, 3.8)); grafico_balanceo(res[mejor], takt, ax); fig.tight_layout(); fig.savefig(f"{pref}_balanceo.png", dpi=150)
    fig, ax = plt.subplots(figsize=(7, 0.5 * len(res[mejor]["util"]) + 1.6)); grafico_utilizacion(res[mejor], True, ax); fig.tight_layout(); fig.savefig(f"{pref}_utilizacion.png", dpi=150)
    ops = [2, 3, 4, 5, 6]
    sens = {k: [simular(p.copia(layout=k, operarios=n), max(2, reps // 2))["buenas"] for n in ops] for k in LAYOUTS}
    fig, ax = plt.subplots(figsize=(8, 4)); grafico_sensibilidad(sens, ops, meta, ax); fig.tight_layout(); fig.savefig(f"{pref}_sensibilidad.png", dpi=150)
    plt.close("all")
    print(f"\nGráficas guardadas en {SALIDAS}")
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--familia", default="solidos", choices=list(FAMILIAS))
    ap.add_argument("--operarios", type=int, default=3)
    ap.add_argument("--reps", type=int, default=5, help="réplicas (turnos simulados) por escenario")
    ap.add_argument("--meta", type=float, default=None, help="meta de unidades por turno")
    ap.add_argument("--produccion-real", type=float, default=None,
                    help="unidades buenas/turno de la mesa manual hoy, para calibrar la sobrecarga manual")
    ap.add_argument("--todo", action="store_true", help="todas las familias con 3 y 4 operarios")
    a = ap.parse_args()

    dfs = []
    combos = [(f, n) for f in FAMILIAS for n in (3, 4)] if a.todo else [(a.familia, a.operarios)]
    for fam, n in combos:
        p = Parametros(familia=fam, operarios=n)
        if a.produccion_real and not a.todo:
            f = calibrar_factor_manual(p, a.produccion_real)
            print(f"Sobrecarga manual calibrada: {f:.2f} (+{(f - 1) * 100:.0f} %)")
            p = p.copia(factor_manual=f)
        print(f"\n=== {FAMILIAS[fam]['nombre']} · {n} operarios ===")
        dfs.append(un_escenario(p, a.reps, a.meta))
    out = SALIDAS / "comparacion_escenarios.xlsx"
    pd.concat(dfs).to_excel(out, index=False)
    print(f"Tabla guardada en {out}")


if __name__ == "__main__":
    main()
