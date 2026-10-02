"""Gráficas con matplotlib (para scripts y reportes)."""
from __future__ import annotations

import matplotlib.pyplot as plt

from .familias import LAYOUTS

GRIS, GRIS_OSC, ACENTO, ROJO = "#AEB9C0", "#7E8D96", "#0B6E7A", "#C8483C"
COLORES_ESTADO = {"trabajo": "#1E9C6B", "ocioso": "#C9A227", "bloqueado": "#C8483C",
                  "paro": "#7A5AA8", "caminando": "#3B7BD4"}
NOMBRES_ESTADO = {"trabajo": "Trabajando", "ocioso": "Esperando", "bloqueado": "Bloqueado",
                  "paro": "Microparo", "caminando": "Desplazándose"}


def _estilo(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#E6EBEE")
    ax.set_axisbelow(True)


def grafico_comparacion(res: dict, meta: float | None = None, ax=None):
    """Barras horizontales de unidades buenas por turno para cada distribución."""
    ax = ax or plt.subplots(figsize=(8, 3.6))[1]
    keys = list(LAYOUTS)
    vals = [res[k]["buenas"] for k in keys]
    sds = [res[k].get("buenas_sd", 0) for k in keys]
    mejor = max(keys, key=lambda k: res[k]["buenas"])
    cols = [ACENTO if k == mejor else (GRIS_OSC if k == "A" else GRIS) for k in keys]
    y = range(len(keys))[::-1]
    ax.barh(list(y), vals, xerr=[2 * s for s in sds], color=cols, ecolor="#555", capsize=3)
    ax.set_yticks(list(y), [LAYOUTS[k]["nombre"] for k in keys])
    base = res["A"]["buenas"]
    for yi, v, k in zip(y, vals, keys):
        txt = f"{v:,.0f}".replace(",", ".") + ("" if k == "A" else f"  ({(v / base - 1) * 100:+.0f} %)")
        ax.text(v, yi, "  " + txt, va="center", fontsize=9)
    if meta:
        ax.axvline(meta, color=ROJO, ls="--", lw=1.2)
        ax.text(meta, len(keys) - 0.4, f"Meta {meta:,.0f}".replace(",", "."), color=ROJO, ha="center", fontsize=8)
    ax.set_xlabel("Unidades buenas por turno")
    ax.set_xlim(0, max(vals + [meta or 0]) * 1.25)
    ax.set_title(f"Mejor distribución: {LAYOUTS[mejor]['nombre']}", loc="left", fontsize=11)
    _estilo(ax)
    return ax


def grafico_balanceo(r: dict, takt: float | None = None, ax=None):
    """Tiempo de ciclo por estación (s/und) frente al takt de la meta."""
    ax = ax or plt.subplots(figsize=(6, 3.6))[1]
    est = r["estaciones"]
    vals = [e.t_ef / e.ops for e in est]
    cu = max(vals)
    cols = [ACENTO if abs(v - cu) < 1e-9 else GRIS for v in vals]
    xs = [f"E{i + 1}\n{e.ops} op." for i, e in enumerate(est)]
    ax.bar(xs, vals, color=cols)
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    if takt:
        ax.axhline(takt, color=ROJO, ls="--", lw=1.2)
        ax.text(len(vals) - 0.5, takt, f"Takt {takt:.1f} s", color=ROJO, ha="right", va="bottom", fontsize=8)
    ax.set_ylabel("s por unidad (estación ÷ operarios)")
    ax.set_title(f"Balanceo · eficiencia {r['eficiencia_balance'] * 100:.0f} %", loc="left", fontsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return ax


def grafico_utilizacion(r: dict, banda=True, ax=None):
    """Barras apiladas del uso del tiempo por operario."""
    ax = ax or plt.subplots(figsize=(6, 0.5 * len(r["util"]) + 1.2))[1]
    U = r["util"]
    etiquetas = [(f"O{i + 1}" + (f" · E{u['estacion'] + 1}" if banda else "")) if u["fijo"] else "Flotante"
                 for i, u in enumerate(U)]
    left = [0.0] * len(U)
    y = list(range(len(U)))[::-1]
    for k, c in COLORES_ESTADO.items():
        w = [u[k] * 100 for u in U]
        ax.barh(y, w, left=left, color=c, label=NOMBRES_ESTADO[k])
        for yi, l, wi in zip(y, left, w):
            if wi > 7:
                ax.text(l + wi / 2, yi, f"{wi:.0f}", ha="center", va="center", color="white", fontsize=8)
        left = [a + b for a, b in zip(left, w)]
    ax.set_yticks(y, etiquetas)
    ax.set_xlim(0, 100)
    ax.set_xlabel("% del tiempo efectivo")
    ax.legend(ncol=5, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, 1.25), frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return ax


def grafico_sensibilidad(sens: dict, operarios: list[int], meta: float | None = None, ax=None):
    """Unidades por turno según número de operarios para cada distribución."""
    ax = ax or plt.subplots(figsize=(8, 4))[1]
    mejor = max(sens, key=lambda k: sens[k][-1])
    for k, v in sens.items():
        ax.plot(operarios, v, marker="o", lw=3 if k == mejor else 1.6,
                ls="--" if k == "A" else "-",
                color=ACENTO if k == mejor else ("#16232B" if k == "A" else GRIS_OSC),
                label=LAYOUTS[k]["nombre"])
    if meta:
        ax.axhline(meta, color=ROJO, ls="--", lw=1.2, label="Meta")
    ax.set_xlabel("Operarios")
    ax.set_ylabel("Unidades buenas por turno")
    ax.set_xticks(operarios)
    ax.legend(fontsize=8, frameon=False)
    ax.grid(color="#E6EBEE")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    return ax
