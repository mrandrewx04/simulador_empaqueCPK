"""Vista de planta animada de la línea.

- `Geometria`: ubica estaciones, unidades en banda y operarios (independiente del dibujo).
- `Planta`: animación en ventana con matplotlib.
- `cuadros_animacion`: genera cuadros para animaciones en Plotly (usado por app.py).

Uso:  python -m simulador.animacion --familia solidos --layout C --operarios 4
"""
from __future__ import annotations

import argparse
import math

from .familias import FAMILIAS, LAYOUTS, Parametros
from .motor import Linea

COLOR_ESTADO = {"trabajo": "#1E9C6B", "listo": "#1E9C6B", "ocioso": "#C9A227", "bloqueado": "#C8483C",
                "paro": "#7A5AA8", "caminando": "#3B7BD4"}


class Geometria:
    def __init__(self, linea: Linea):
        self.linea = linea
        self.L = LAYOUTS[linea.p.layout]
        S = len(linea.cfg.estaciones)
        if not self.L["banda"]:
            self.pts = None
            self.mesa = (2, 1.5, 8, 2)  # x, y, ancho, alto
            self.xlim, self.ylim = (0, 12.5), (-0.3, 5.3)
            self.st_xy = []
            return
        self.pts = [(1, 4), (11, 4), (11, 1), (1, 1)] if self.L["flex"] else [(1, 2), (11, 2)]
        self.seg = [math.dist(self.pts[i], self.pts[i + 1]) for i in range(len(self.pts) - 1)]
        self.largo = sum(self.seg)
        m = 0.6
        self.st_s = [self.largo / 2] if S == 1 else [m + (self.largo - 2 * m) * i / (S - 1) for i in range(S)]
        self.st_xy = [self.en(s)[:2] for s in self.st_s]
        self.xlim = (-0.3, 12.5)
        self.ylim = (-0.3, 5.0) if self.L["flex"] else (0.6, 3.4)

    def en(self, s):
        s = max(0, min(self.largo, s))
        for i, d in enumerate(self.seg):
            if s <= d or i == len(self.seg) - 1:
                (x0, y0), (x1, y1) = self.pts[i], self.pts[i + 1]
                f = s / d if d else 0
                return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, (x1 - x0) / d, (y1 - y0) / d
            s -= d

    def items(self):
        ln = self.linea
        if not self.L["banda"]:
            return []
        c, pts = ln.cfg, []
        for i in range(1, len(ln.buf)):
            s_fin, s_ini, q = self.st_s[i] - 0.3, self.st_s[i - 1] + 0.3, 0
            paso = min(0.25, (s_fin - s_ini) / (c.cap + 2))
            for arr in ln.buf[i]:
                if arr <= ln.t:
                    s = s_fin - q * paso
                    q += 1
                else:
                    f = 1 - (arr - ln.t) / max(0.01, c.transito)
                    s = min(s_ini + (s_fin - s_ini) * f, s_fin - q * paso)
                pts.append(self.en(s)[:2])
        return pts

    def operarios(self):
        ln, res = self.linea, []
        for idx, o in enumerate(ln.ops):
            if not self.L["banda"]:
                cols = math.ceil(len(ln.ops) / 2)
                xy = (2 + 8 * ((idx // 2) + 0.5) / cols, 4.1 if idx % 2 == 0 else 0.9)
            else:
                mismos = sum(1 for j, q in enumerate(ln.ops) if q.fijo and q.est == o.est and j < idx)
                x, y, dx, dy = self.en(self.st_s[o.est])
                nx, ny = -dy, dx
                if not o.fijo:
                    off, along = -0.75, 0
                elif self.L["doble_lado"]:
                    n_est = ln.cfg.estaciones[o.est].ops
                    off, along = (0.6 if mismos % 2 else -0.6), (mismos // 2) * 0.55 - (0.27 if n_est > 2 else 0)
                else:
                    off, along = (0.6 if self.L["flex"] else -0.6), mismos * 0.5
                xy = (x + nx * off + dx * along, y + ny * off + dy * along)
            etiqueta = f"O{idx + 1}" if o.fijo else "F"
            res.append((xy[0], xy[1], o.st, etiqueta))
        return res


def cuadros_animacion(p: Parametros, minutos=20, seg_por_cuadro=10, dt=0.25):
    """Corre la línea `minutos` y devuelve una lista de cuadros con posiciones."""
    ln = Linea(p)
    g = Geometria(ln)
    cuadros = []
    pasos = int(seg_por_cuadro / dt)
    while ln.t < min(ln.efectivo, minutos * 60):
        for _ in range(pasos):
            ln.paso(dt)
        cuadros.append({"t": ln.t, "buenas": ln.buenas, "items": g.items(), "ops": g.operarios()})
    return g, cuadros


def figura_plotly(p: Parametros, minutos=15, seg_por_cuadro=5):
    """Figura Plotly animada (botón Reproducir) con la vista de planta."""
    import plotly.graph_objects as go
    g, cuadros = cuadros_animacion(p, minutos=minutos, seg_por_cuadro=seg_por_cuadro)

    def trazas(c):
        it = c["items"] or [(-5, -5)]
        return [go.Scatter(x=[x for x, _ in it], y=[y for _, y in it], mode="markers",
                           marker=dict(symbol="square", size=11, color="#E9D7B5", line=dict(color="#9C8158", width=1)),
                           name="Unidades", showlegend=False, hoverinfo="skip"),
                go.Scatter(x=[o[0] for o in c["ops"]], y=[o[1] for o in c["ops"]], mode="markers+text",
                           text=[o[3] for o in c["ops"]], textfont=dict(color="white", size=11),
                           hovertext=[o[2] for o in c["ops"]], hoverinfo="text",
                           marker=dict(size=34, color=[COLOR_ESTADO.get(o[2], "#1E9C6B") for o in c["ops"]],
                                       line=dict(color="white", width=2)), name="Operarios", showlegend=False)]

    fig = go.Figure()
    if g.pts is None:
        x, y, w, h = g.mesa
        fig.add_shape(type="rect", x0=x, y0=y, x1=x + w, y1=y + h, fillcolor="#D7DEE2", line_width=0, layer="below")
    else:
        fig.add_trace(go.Scatter(x=[q[0] for q in g.pts], y=[q[1] for q in g.pts], mode="lines",
                                 line=dict(color="#AEB9C0", width=26), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=[q[0] for q in g.st_xy], y=[q[1] for q in g.st_xy], mode="markers+text",
                                 text=[f"E{i + 1}" for i in range(len(g.st_xy))], textfont=dict(color="white", size=10),
                                 marker=dict(size=22, color="#16232B"), hoverinfo="skip", showlegend=False))
    n0 = len(fig.data)  # trazas fijas debajo; las animadas encima
    for tr in trazas(cuadros[0]):
        fig.add_trace(tr)
    fig.frames = [go.Frame(data=trazas(c), traces=[n0, n0 + 1], name=str(i),
                           layout=go.Layout(title=dict(text=f"t = {int(c['t'] // 60)} min {int(c['t'] % 60):02d} s · {c['buenas']} und buenas")))
                  for i, c in enumerate(cuadros)]
    fig.update_layout(
        height=430 if g.L["flex"] else 330, title=dict(text="t = 0 min"),
        xaxis=dict(range=list(g.xlim), visible=False), yaxis=dict(range=list(g.ylim), visible=False, scaleanchor="x"),
        margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="white",
        updatemenus=[dict(type="buttons", direction="left", x=0, y=-0.02, xanchor="left", yanchor="top", buttons=[
            dict(label="Reproducir", method="animate",
                 args=[None, dict(frame=dict(duration=120, redraw=True), fromcurrent=True, transition=dict(duration=0))]),
            dict(label="Pausa", method="animate",
                 args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(active=0, x=0.2, len=0.8, y=-0.02, currentvalue=dict(visible=False), pad=dict(t=0),
                      steps=[dict(method="animate", label="", args=[[str(i)], dict(mode="immediate", frame=dict(duration=0, redraw=True))])
                             for i in range(len(cuadros))])])
    return fig


class Planta:
    """Animación en ventana (matplotlib)."""

    def __init__(self, p: Parametros, velocidad=30, fps=20):
        import matplotlib.pyplot as plt
        from matplotlib.patches import Circle, Rectangle
        self.plt = plt
        self.vel, self.fps = velocidad, fps
        self.linea = Linea(p)
        self.g = Geometria(self.linea)
        self.fig, self.ax = plt.subplots(figsize=(12, 5 if self.g.L["flex"] else 3.6))
        ax = self.ax
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_xlim(*self.g.xlim); ax.set_ylim(*self.g.ylim)
        if self.g.pts is None:
            x, y, w, h = self.g.mesa
            ax.add_patch(Rectangle((x, y), w, h, color="#D7DEE2"))
            ax.text(x + w / 2, y + h / 2, "MESA DE ACONDICIONAMIENTO", ha="center", va="center", color="#5A6B75")
        else:
            xs, ys = zip(*self.g.pts)
            ax.plot(xs, ys, color="#AEB9C0", lw=18, solid_capstyle="butt", zorder=1)
            for i, (x, y) in enumerate(self.g.st_xy):
                ax.add_patch(Circle((x, y), 0.18, color="#16232B", zorder=3))
                ax.text(x, y, f"E{i + 1}", color="white", ha="center", va="center", fontsize=7, zorder=4)
        self.items = ax.scatter([], [], marker="s", s=60, c="#E9D7B5", edgecolors="#9C8158", zorder=2)
        self.opsc = ax.scatter([], [], s=420, zorder=5, edgecolors="white", linewidths=2)
        self.txt = ax.text(self.g.xlim[0], self.g.ylim[0], "", fontsize=10, family="monospace")
        ax.set_title(f"{LAYOUTS[p.layout]['nombre']} · {p.operarios} operarios · {FAMILIAS[p.familia]['nombre']}", loc="left")
        for k in ("trabajo", "ocioso", "bloqueado", "paro", "caminando"):
            ax.scatter([], [], c=COLOR_ESTADO[k], s=60, label=k)
        ax.legend(loc="upper right", fontsize=8, ncol=5, frameon=False)

    def _frame(self, _):
        ln = self.linea
        for _ in range(max(1, int(self.vel / self.fps / 0.25))):
            if ln.t < ln.efectivo:
                ln.paso(0.25)
        self.items.set_offsets(self.g.items() or [(-10, -10)])
        ops = self.g.operarios()
        self.opsc.set_offsets([(x, y) for x, y, _, _ in ops])
        self.opsc.set_color([COLOR_ESTADO.get(s, "#1E9C6B") for _, _, s, _ in ops])
        h = ln.t / 3600
        ritmo = ln.buenas / h if h > 0.03 else 0
        self.txt.set_text(f"t = {int(ln.t // 3600)} h {int(ln.t % 3600 // 60):02d} min   "
                          f"buenas = {ln.buenas:,}   ritmo = {ritmo:,.0f} und/h")
        return self.items, self.opsc, self.txt

    def mostrar(self):
        from matplotlib.animation import FuncAnimation
        self.anim = FuncAnimation(self.fig, self._frame, interval=1000 / self.fps, cache_frame_data=False)
        self.plt.show()


def main():
    ap = argparse.ArgumentParser(description="Animación de la línea de empaque")
    ap.add_argument("--familia", default="solidos", choices=list(FAMILIAS))
    ap.add_argument("--layout", default="C", choices=list(LAYOUTS))
    ap.add_argument("--operarios", type=int, default=4)
    ap.add_argument("--velocidad", type=float, default=30, help="segundos simulados por segundo real")
    a = ap.parse_args()
    Planta(Parametros(familia=a.familia, layout=a.layout, operarios=a.operarios), a.velocidad).mostrar()


if __name__ == "__main__":
    main()
