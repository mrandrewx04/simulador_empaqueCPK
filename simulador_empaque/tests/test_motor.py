"""Pruebas del motor.  Ejecutar:  python -m pytest -q"""
import math

from simulador import Parametros, balancear, configurar, simular, calibrar_escala


def test_balanceo_minimiza_cuello():
    b = balancear([4, 5, 3.5, 3, 3.5, 2.5], 3, 3)
    assert math.isclose(b.cuello, 9.0)  # [4+5] [3.5+3] [3.5+2.5]
    assert sum(b.ops) == 3


def test_linea_determinista_coincide_con_calculo():
    # sin variabilidad, sin paros, sin rechazo: producción = tiempo efectivo / cuello
    p = Parametros(familia="solidos", layout="B", operarios=6, cv=0, paro_hora=0, rechazo=0)
    r = simular(p, reps=1)
    esperado = p.efectivo_seg / 5.0  # tarea más larga = 5 s
    assert abs(r["buenas"] - esperado) / esperado < 0.01


def test_mesa_manual_analitica():
    p = Parametros(familia="solidos", layout="A", operarios=3, cv=0, paro_hora=0, rechazo=0)
    r = simular(p, reps=1)
    esperado = p.efectivo_seg / (21.5 * 1.35) * 3
    assert abs(r["buenas"] - esperado) / esperado < 0.01


def test_distribucion_c_comparte_cuello():
    cfg = configurar(Parametros(familia="solidos", layout="C", operarios=4))
    assert max(e.ops for e in cfg.estaciones) >= 2


def test_calibrar_escala_reproduce_estandar():
    p = Parametros(familia="solidos", operarios=3)
    s = calibrar_escala(p, 761)
    r = simular(p.copia(layout="A", escala_tiempos=s), reps=3)
    assert abs(r["por_hora_efectiva"] - 761) / 761 < 0.03
