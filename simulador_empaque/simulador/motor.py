"""Motor de simulación de la línea de acondicionamiento y embalaje.

Simulación de paso de tiempo fijo (dt = 0,25 s por defecto) de un turno:
- Estaciones en serie, cada una con 1 o más operarios en paralelo.
- Banda entre estaciones con tiempo de tránsito y capacidad limitada
  (si se llena, el operario anterior queda BLOQUEADO).
- Variabilidad lognormal de los tiempos, microparos aleatorios y rechazo.
- Operario flotante (layout D) que va a la estación con más unidades en espera.
"""
from __future__ import annotations

import math
import random
from collections import deque
from dataclasses import dataclass, field
from statistics import mean, stdev

from .familias import LAYOUTS, Parametros

ESTADOS = ("trabajo", "ocioso", "bloqueado", "paro", "caminando")


# ---------------------------------------------------------------- balanceo
@dataclass
class Balance:
    grupos: list          # [(inicio, fin)] índices de tareas por estación
    cargas: list          # s estándar por estación
    ops: list             # operarios por estación
    cuello: float         # max(carga/ops)
    desv: float


def balancear(tiempos: list[float], n_est: int, n_ops: int) -> Balance:
    """Busca la partición contigua de tareas en `n_est` estaciones y el reparto de
    `n_ops` operarios que minimiza el cuello de botella (carga / operarios)."""
    n = len(tiempos)
    n_est = max(1, min(n_est, n))
    mejor: Balance | None = None

    def evalua(grupos):
        nonlocal mejor
        cargas = [sum(tiempos[a:b]) for a, b in grupos]
        ops = [1] * len(cargas)
        for _ in range(n_ops - len(cargas)):
            k = max(range(len(cargas)), key=lambda i: cargas[i] / ops[i])
            ops[k] += 1
        cuello = max(c / o for c, o in zip(cargas, ops))
        desv = sum((c / o - cuello) ** 2 for c, o in zip(cargas, ops))
        if (mejor is None or cuello < mejor.cuello - 1e-9
                or (abs(cuello - mejor.cuello) < 1e-9 and desv < mejor.desv)):
            mejor = Balance(list(grupos), cargas, ops, cuello, desv)

    def rec(inicio, grupos):
        if len(grupos) == n_est - 1:
            evalua(grupos + [(inicio, n)])
            return
        for fin in range(inicio + 1, n - (n_est - 1 - len(grupos)) + 1):
            rec(fin, grupos + [(inicio, fin)])

    rec(0, [])
    return mejor


@dataclass
class Estacion:
    tareas: list[int]
    nombres: list[str]
    carga: float       # s estándar (sin factor)
    ops: int
    t_ef: float = 0.0  # s efectivos (con factor manual / banda)


@dataclass
class Configuracion:
    estaciones: list[Estacion]
    flex: int
    factor: float
    transito: float
    cap: int
    banda: bool


def configurar(p: Parametros) -> Configuracion:
    tareas = p.lista_tareas()
    t = [x.t for x in tareas]
    L = LAYOUTS[p.layout]
    n = p.operarios
    flex = 0
    if not L["banda"]:
        est = [Estacion(list(range(len(t))), [x.nombre for x in tareas], sum(t), n)]
    else:
        n_fijos = n
        if L["flex"]:
            flex = 1 if n >= 2 else 0
            n_fijos = n - flex
            n_est = min(n_fijos, len(t))
        elif L["doble_lado"]:
            n_est = max(1, min(n - 1, len(t)))
        else:
            n_est = min(n, len(t))
        b = balancear(t, n_est, n_fijos)
        if L["doble_lado"]:
            for k in range(2, n):
                bb = balancear(t, min(k, len(t)), n_fijos)
                if bb.cuello < b.cuello - 1e-9 or (abs(bb.cuello - b.cuello) < 1e-9 and bb.desv < b.desv):
                    b = bb
        est = [Estacion(list(range(a, z)), [tareas[i].nombre for i in range(a, z)], b.cargas[i], b.ops[i])
               for i, (a, z) in enumerate(b.grupos)]
    factor = p.factor_banda if L["banda"] else p.factor_manual
    for e in est:
        e.t_ef = e.carga * factor
    transito = p.dist_est / (p.vel_banda / 60) if L["banda"] else 0.0
    cap = max(1, int(p.dist_est // p.paso)) if L["banda"] else 10 ** 9
    return Configuracion(est, flex, factor, transito, cap, L["banda"])


# ---------------------------------------------------------------- simulación
@dataclass
class Operario:
    est: int
    fijo: bool
    st: str = "ocioso"
    rest: float = 0.0
    rest_trabajo: float = 0.0
    pieza: bool = False
    desde: int | None = None
    acc: dict = field(default_factory=lambda: {k: 0.0 for k in ESTADOS})


class Linea:
    """Una corrida (un turno) de la línea. Use `paso()` para animar o `correr()`."""

    def __init__(self, p: Parametros):
        self.p = p
        self.cfg = configurar(p)
        self.rng = random.Random(p.semilla * 9973 + 17)
        self.t = 0.0
        S = len(self.cfg.estaciones)
        self.buf = [deque() for _ in range(S)]  # buf[i] = tiempos de llegada a la entrada de i
        self.ops: list[Operario] = []
        for i, e in enumerate(self.cfg.estaciones):
            self.ops += [Operario(i, True) for _ in range(e.ops)]
        self.ops += [Operario(0, False) for _ in range(self.cfg.flex)]
        self.buenas = 0
        self.rechazadas = 0
        self.wip_acc = 0.0
        self.efectivo = p.efectivo_seg
        s2 = math.log(1 + p.cv ** 2)
        self._mu_adj, self._sig = -s2 / 2, math.sqrt(s2)

    # -- auxiliares
    def _tiempo(self, i):
        m = self.cfg.estaciones[i].t_ef
        if self.p.cv <= 0:
            return m
        return m * math.exp(self._mu_adj + self._sig * self.rng.gauss(0, 1))

    def _puede_salir(self, i):
        return i == len(self.buf) - 1 or len(self.buf[i + 1]) < self.cfg.cap

    def _tomar(self, i):
        if i == 0:
            return True
        b = self.buf[i]
        if b and b[0] <= self.t:
            b.popleft()
            return True
        return False

    def _disponibles(self, i):
        return sum(1 for x in self.buf[i] if x <= self.t)

    def _entregar(self, i):
        if i == len(self.buf) - 1:
            if self.rng.random() < self.p.rechazo / 100:
                self.rechazadas += 1
            else:
                self.buenas += 1
        else:
            self.buf[i + 1].append(self.t + self.cfg.transito)

    # -- avance
    def paso(self, dt=0.25):
        S = len(self.buf)
        p = self.p
        for o in self.ops:
            if o.st in ("trabajo", "paro", "caminando"):
                o.acc[o.st] += dt
                o.rest -= dt
                if o.rest > 0:
                    continue
                if o.st == "paro":
                    o.st, o.rest = "trabajo", o.rest_trabajo
                    continue
                o.st = "ocioso" if o.st == "caminando" else "listo"
            if o.st in ("listo", "bloqueado"):
                if self._puede_salir(o.est):
                    self._entregar(o.est)
                    o.st, o.pieza = "ocioso", False
                else:
                    o.st = "bloqueado"
                    o.acc["bloqueado"] += dt
                    continue
            if o.st == "ocioso":
                if not o.fijo:
                    mejor, mx = -1, 0
                    for i in range(1, S):
                        d = self._disponibles(i)
                        if d > mx:
                            mx, mejor = d, i
                    if mejor < 0 and self._puede_salir(0) and len(self.buf[min(1, S - 1)]) < self.cfg.cap * 0.5:
                        mejor = 0
                    if mejor >= 0 and mejor != o.est:
                        o.desde, o.est = o.est, mejor
                        o.st, o.rest = "caminando", p.caminar_seg
                        continue
                    if mejor < 0:
                        o.acc["ocioso"] += dt
                        continue
                if self._tomar(o.est):
                    o.pieza = True
                    tt = self._tiempo(o.est)
                    if self.rng.random() < p.paro_hora * tt / 3600:
                        o.st, o.rest, o.rest_trabajo = "paro", self.rng.expovariate(1 / p.paro_seg), tt
                    else:
                        o.st, o.rest = "trabajo", tt
                else:
                    o.acc["ocioso"] += dt
        self.wip_acc += sum(len(b) for b in self.buf[1:]) * dt
        self.t += dt

    def correr(self, dt=0.25) -> dict:
        while self.t < self.efectivo:
            self.paso(dt)
        return self.resultados()

    def resultados(self) -> dict:
        p, c = self.p, self.cfg
        est = c.estaciones
        n_ops = len(self.ops)
        total_cont = sum(e.carga for e in est)
        t_plan = (p.turno_min - p.pausas_min) * 60
        total = self.buenas + self.rechazadas
        disponibilidad = self.efectivo / t_plan
        rendimiento = total * (total_cont / n_ops) / self.efectivo if self.efectivo else 0
        calidad = self.buenas / total if total else 1
        util = []
        for o in self.ops:
            T = sum(o.acc.values()) or 1
            util.append({"estacion": o.est, "fijo": o.fijo, **{k: o.acc[k] / T for k in ESTADOS}})
        return {
            "buenas": self.buenas,
            "rechazadas": self.rechazadas,
            "por_hora": self.buenas / p.horas_plan,
            "por_hora_efectiva": self.buenas / (self.efectivo / 3600),
            "por_operario_hora": self.buenas / p.horas_plan / n_ops,
            "disponibilidad": disponibilidad,
            "rendimiento": rendimiento,
            "calidad": calidad,
            "oee": disponibilidad * rendimiento * calidad,
            "wip_prom": self.wip_acc / max(1, self.t),
            "util": util,
            "cuello_seg": max(e.carga / e.ops for e in est) * c.factor,
            "eficiencia_balance": total_cont / (len(est) * max(e.carga for e in est)),
            "estaciones": est,
            "flex": c.flex,
        }


def simular(p: Parametros, reps: int = 5, dt: float = 0.25) -> dict:
    """Corre `reps` turnos con semillas distintas y promedia."""
    rs = [Linea(p.copia(semilla=p.semilla + k)).correr(dt) for k in range(reps)]
    num = ["buenas", "por_hora", "por_hora_efectiva", "por_operario_hora", "oee", "disponibilidad",
           "rendimiento", "calidad", "wip_prom"]
    out = dict(rs[0])
    for k in num:
        out[k] = mean(r[k] for r in rs)
    out["buenas_sd"] = stdev([r["buenas"] for r in rs]) if reps > 1 else 0.0
    out["util"] = [{"estacion": u["estacion"], "fijo": u["fijo"],
                    **{k: mean(r["util"][i][k] for r in rs) for k in ESTADOS}}
                   for i, u in enumerate(rs[0]["util"])]
    out["reps"] = reps
    return out


def comparar(p: Parametros, reps: int = 5, dt: float = 0.25) -> dict:
    """Simula las 4 distribuciones con los mismos parámetros."""
    return {k: simular(p.copia(layout=k), reps, dt) for k in LAYOUTS}


def calibrar_factor_manual(p: Parametros, produccion_turno: float, reps: int = 2) -> float:
    """Ajusta la sobrecarga de la mesa manual para que el layout A reproduzca la producción real."""
    lo, hi = 0.6, 3.0
    for _ in range(16):
        mid = (lo + hi) / 2
        r = simular(p.copia(layout="A", factor_manual=mid), reps)
        lo, hi = (mid, hi) if r["buenas"] > produccion_turno else (lo, mid)
    return (lo + hi) / 2


def calibrar_escala(p: Parametros, und_hora_estandar: float, reps: int = 2) -> float:
    """Escala los tiempos de tarea para que la mesa manual (layout A) produzca
    `und_hora_estandar` por hora efectiva. Útil con el archivo de estándares."""
    lo, hi = 0.02, 20.0
    for _ in range(22):
        mid = math.sqrt(lo * hi)
        r = simular(p.copia(layout="A", escala_tiempos=mid), reps)
        lo, hi = (mid, hi) if r["por_hora_efectiva"] > und_hora_estandar else (lo, mid)
    return math.sqrt(lo * hi)
