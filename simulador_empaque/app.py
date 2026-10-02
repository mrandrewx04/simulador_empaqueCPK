"""Simulador Línea de Empaque — aplicación interactiva.

Ejecutar:  streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulador import (FAMILIAS, LAYOUTS, Parametros, Tarea, calibrar_escala, calibrar_factor_manual,
                       comparar, simular)
from simulador.animacion import figura_plotly
from simulador.estandares import leer_estandares

ARCHIVO_STD = Path(__file__).parent / "datos" / "tiempos_acond.xlsx"
ACENTO, GRIS, GRIS_OSC, ROJO = "#0B6E7A", "#AEB9C0", "#7E8D96", "#C8483C"
ESTADOS = {"trabajo": ("Trabajando", "#1E9C6B"), "ocioso": ("Esperando", "#C9A227"),
           "bloqueado": ("Bloqueado", "#C8483C"), "paro": ("Microparo", "#7A5AA8"),
           "caminando": ("Desplazándose", "#3B7BD4")}

st.set_page_config(page_title="Simulador Línea de Empaque", layout="wide")
st.title("Simulador Línea de Empaque")
st.caption("Acondicionamiento y embalaje · comparación de distribución de personal con banda transportadora")


def fmt(x, d=0):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


@st.cache_data(show_spinner=False)
def cargar_std(ruta: str):
    return leer_estandares(ruta)


@st.cache_data(show_spinner="Simulando las 4 distribuciones…")
def _comparar(pd_dict, tareas, reps):
    p = Parametros(**pd_dict, tareas=[Tarea(*t) for t in tareas])
    return comparar(p, reps)


@st.cache_data(show_spinner="Calculando sensibilidad por número de operarios…")
def _sens(pd_dict, tareas, ops):
    p = Parametros(**pd_dict, tareas=[Tarea(*t) for t in tareas])
    return {k: [simular(p.copia(layout=k, operarios=n), 3)["buenas"] for n in ops] for k in LAYOUTS}


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.header("Parámetros")
    familia = st.selectbox("Familia de producto", list(FAMILIAS), format_func=lambda k: FAMILIAS[k]["nombre"])
    operarios = st.select_slider("Operarios en la línea", [2, 3, 4, 5, 6], value=3)
    layout = st.radio("Distribución a detallar", list(LAYOUTS), format_func=lambda k: LAYOUTS[k]["nombre"],
                      horizontal=False, index=2)
    st.caption(LAYOUTS[layout]["descripcion"])

    st.subheader("Turno")
    c1, c2 = st.columns(2)
    turno = c1.number_input("Turno (min)", 60, 720, 480, 10)
    pausas = c2.number_input("Pausas (min)", 0, 120, 30, 5)
    despejes = c1.number_input("Despejes/turno", 0, 10, 1)
    despeje_min = c2.number_input("Min por despeje", 0, 120, 20, 5)
    meta = st.number_input("Meta del turno (und)", 0, 50000, 3600, 100)

    with st.expander("Parámetros avanzados"):
        factor_manual = st.number_input("Sobrecarga mesa manual (×)", 1.0, 3.0,
                                        st.session_state.get("factor_manual", 1.35), 0.01)
        factor_banda = st.number_input("Factor en banda (×)", 0.7, 2.0, 1.0, 0.01)
        cv = st.number_input("Variabilidad de tiempos (CV)", 0.0, 1.0, 0.25, 0.05)
        paro_hora = st.number_input("Microparos por operario-hora", 0.0, 60.0, 4.0, 1.0)
        paro_seg = st.number_input("Duración media microparo (s)", 0.0, 600.0, 45.0, 5.0)
        rechazo = st.number_input("Rechazo en inspección (%)", 0.0, 50.0, 0.5, 0.1)
        dist_est = st.number_input("Distancia entre estaciones (m)", 0.3, 10.0, 1.2, 0.1)
        vel_banda = st.number_input("Velocidad de banda (m/min)", 0.5, 60.0, 6.0, 0.5)
        paso_und = st.number_input("Espacio por unidad en banda (m)", 0.05, 1.0, 0.15, 0.01)
        caminar = st.number_input("Desplazamiento del flotante (s)", 0.0, 60.0, 3.0, 1.0)
        reps = st.slider("Réplicas por escenario", 2, 20, 5)

with st.expander("Tiempos estándar por tarea (s/und) — editar", expanded=False):
    clave = f"tareas_{familia}"
    if clave not in st.session_state:
        st.session_state[clave] = pd.DataFrame([{"Tarea": t.nombre, "Segundos": t.t} for t in FAMILIAS[familia]["tareas"]])
    tdf = st.data_editor(st.session_state[clave], num_rows="dynamic", use_container_width=True, key=f"ed_{familia}",
                         hide_index=True, column_config={
                             "Tarea": st.column_config.TextColumn("Tarea", width="large"),
                             "Segundos": st.column_config.NumberColumn("Segundos por unidad", min_value=0.1, step=0.1, format="%.1f")})
    tdf = tdf.dropna()
    tdf = tdf[tdf["Segundos"] > 0]
    if st.button("Restaurar tiempos de referencia"):
        del st.session_state[clave]
        st.rerun()
    st.caption(f"Contenido total de trabajo: **{fmt(tdf['Segundos'].sum(), 1)} s**. "
               "Valores de referencia: reemplácelos por cronometraje.")


params = dict(familia=familia, layout=layout, operarios=operarios, turno_min=turno, pausas_min=pausas,
              despejes=despejes, despeje_min=despeje_min, cv=cv, factor_manual=factor_manual,
              factor_banda=factor_banda, paro_hora=paro_hora, paro_seg=paro_seg, rechazo=rechazo,
              dist_est=dist_est, vel_banda=vel_banda, paso=paso_und, caminar_seg=caminar,
              escala_tiempos=st.session_state.get("escala", 1.0))
tareas = tuple((r.Tarea, float(r.Segundos)) for r in tdf.itertuples())
P = Parametros(**params, tareas=[Tarea(*t) for t in tareas])

# ------------------------------------------------------------------ calibración
with st.expander("Calibrar con datos reales", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Con la producción actual de la mesa manual**")
        real = st.number_input("Unidades buenas por turno hoy", 0, 50000, 0, 50)
        if st.button("Calibrar sobrecarga manual", disabled=real <= 0):
            f = calibrar_factor_manual(P, real)
            st.session_state["factor_manual"] = round(f, 2)
            st.success(f"Sobrecarga estimada: +{(f - 1) * 100:.0f} %. Valor cargado en parámetros avanzados.")
            st.rerun()
    with c2:
        st.markdown("**Con un producto del archivo de estándares**")
        if ARCHIVO_STD.exists():
            dstd = cargar_std(str(ARCHIVO_STD))
            dfam = dstd[(dstd["familia"] == familia) & dstd["estandar"].notna()]
            opciones = dfam.index.tolist()
            sel = st.selectbox("Producto", opciones, format_func=lambda i: f"{dfam.at[i, 'PRODUCTO']} · {fmt(dfam.at[i, 'estandar'])} und/h")
            if st.button("Calibrar con este estándar (3 personas, mesa manual)"):
                s = calibrar_escala(P.copia(operarios=3, escala_tiempos=1.0), float(dfam.at[sel, "estandar"]))
                st.session_state["escala"] = s
                st.success(f"Tiempos escalados ×{s:.2f} para reproducir {fmt(dfam.at[sel, 'estandar'])} und/h.")
                st.rerun()
        else:
            st.info("Ponga el archivo de estándares en datos/tiempos_acond.xlsx")
        if st.session_state.get("escala", 1.0) != 1.0:
            st.caption(f"Escala de tiempos activa: ×{st.session_state['escala']:.2f}")
            if st.button("Quitar escala"):
                st.session_state["escala"] = 1.0
                st.rerun()

# ------------------------------------------------------------------ resultados
pd_dict = {k: v for k, v in params.items()}
res = _comparar(pd_dict, tareas, reps)
mejor = max(res, key=lambda k: res[k]["buenas"])
base = res["A"]["buenas"]

tab1, tab2, tab3, tab4 = st.tabs(["Comparación", "Detalle de la distribución", "Sensibilidad", "Vista de planta"])

with tab1:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Mejor distribución", LAYOUTS[mejor]["corto"])
    k2.metric("Und/turno", fmt(res[mejor]["buenas"]), f"{(res[mejor]['buenas'] / base - 1) * 100:+.0f} % vs manual")
    k3.metric("OEE", f"{res[mejor]['oee'] * 100:.0f} %", f"{(res[mejor]['oee'] - res['A']['oee']) * 100:+.0f} pts")
    k4.metric("Cumple meta", "Sí" if res[mejor]["buenas"] >= meta else "No")

    keys = list(LAYOUTS)[::-1]
    fig = go.Figure(go.Bar(
        x=[res[k]["buenas"] for k in keys], y=[LAYOUTS[k]["nombre"] for k in keys], orientation="h",
        marker_color=[ACENTO if k == mejor else (GRIS_OSC if k == "A" else GRIS) for k in keys],
        text=[fmt(res[k]["buenas"]) + ("" if k == "A" else f"  ({(res[k]['buenas'] / base - 1) * 100:+.0f} %)") for k in keys],
        textposition="outside"))
    if meta:
        fig.add_vline(meta, line_dash="dash", line_color=ROJO, annotation_text=f"Meta {fmt(meta)}")
    fig.update_layout(height=320, margin=dict(l=10, r=40, t=20, b=30), xaxis_title="Unidades buenas por turno")
    st.plotly_chart(fig, use_container_width=True)

    tabla = pd.DataFrame([{
        "Distribución": LAYOUTS[k]["nombre"], "Und/turno": round(r["buenas"]), "± (2 desv.)": round(2 * r["buenas_sd"]), "Und/h": round(r["por_hora"]),
        "Und/operario·h": round(r["por_operario_hora"], 1), "Cambio vs manual": f"{(r['buenas'] / base - 1) * 100:+.0f} %",
        "OEE": f"{r['oee'] * 100:.0f} %", "Balanceo": f"{r['eficiencia_balance'] * 100:.0f} %",
        "WIP medio": round(r["wip_prom"], 1), "Cumple meta": "Sí" if r["buenas"] >= meta else "No"}
        for k, r in res.items()])
    st.dataframe(tabla, use_container_width=True, hide_index=True)
    st.download_button("Descargar tabla (CSV)", tabla.to_csv(index=False).encode("utf-8-sig"),
                       "comparacion.csv", "text/csv")

with tab2:
    r = res[layout]
    st.subheader(LAYOUTS[layout]["nombre"])
    for i, e in enumerate(r["estaciones"]):
        nom = f"E{i + 1}" if LAYOUTS[layout]["banda"] else "Mesa"
        st.markdown(f"**{nom}** · {e.ops} operario(s) · {fmt(e.carga, 1)} s — {' → '.join(e.nombres)}")
    if r["flex"]:
        st.markdown("**F** · operario flotante: apoya la estación con más unidades en espera")
    c1, c2 = st.columns(2)
    vals = [e.t_ef / e.ops for e in r["estaciones"]]
    cu = max(vals)
    fb = go.Figure(go.Bar(x=[f"E{i + 1} · {e.ops} op" for i, e in enumerate(r["estaciones"])], y=vals,
                          marker_color=[ACENTO if abs(v - cu) < 1e-9 else GRIS for v in vals],
                          text=[f"{v:.1f}" for v in vals], textposition="outside"))
    takt = P.efectivo_seg / meta if meta else None
    if takt:
        fb.add_hline(takt, line_dash="dash", line_color=ROJO, annotation_text=f"Takt {takt:.1f} s")
    fb.update_layout(title=f"Balanceo · eficiencia {r['eficiencia_balance'] * 100:.0f} %", height=360,
                     yaxis_title="s por unidad (estación ÷ operarios)", margin=dict(t=50, b=30))
    c1.plotly_chart(fb, use_container_width=True)
    U = r["util"]
    etq = [(f"O{i + 1}" + (f" · E{u['estacion'] + 1}" if LAYOUTS[layout]["banda"] else "")) if u["fijo"] else "Flotante"
           for i, u in enumerate(U)]
    fu = go.Figure([go.Bar(y=etq, x=[u[k] * 100 for u in U], name=n, orientation="h", marker_color=c,
                           text=[f"{u[k] * 100:.0f}" if u[k] > 0.07 else "" for u in U])
                    for k, (n, c) in ESTADOS.items()])
    fu.update_layout(barmode="stack", title="Uso del tiempo por operario (%)", height=360,
                     yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=-0.2), margin=dict(t=50))
    c2.plotly_chart(fu, use_container_width=True)

with tab3:
    ops = [2, 3, 4, 5, 6]
    sens = _sens(pd_dict, tareas, ops)
    fs = go.Figure()
    for k, v in sens.items():
        fs.add_trace(go.Scatter(x=ops, y=v, mode="lines+markers", name=LAYOUTS[k]["nombre"],
                                line=dict(width=4 if k == mejor else 2, dash="dash" if k == "A" else "solid",
                                          color=ACENTO if k == mejor else ("#16232B" if k == "A" else GRIS_OSC))))
    if meta:
        fs.add_hline(meta, line_dash="dash", line_color=ROJO, annotation_text="Meta")
    fs.update_layout(height=420, xaxis_title="Operarios", yaxis_title="Unidades buenas por turno")
    st.plotly_chart(fs, use_container_width=True)
    filas = []
    for k, v in sens.items():
        n_min = next((n for n, x in zip(ops, v) if x >= meta), None) if meta else None
        filas.append({"Distribución": LAYOUTS[k]["nombre"], **{f"{n} op": round(x) for n, x in zip(ops, v)},
                      "Operarios para la meta": n_min or "más de 6"})
    st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True)

with tab4:
    minutos = st.slider("Minutos a animar", 5, 60, 15)
    fa = figura_plotly(P, minutos=minutos)
    st.plotly_chart(fa, use_container_width=True)
    st.caption("Colores: verde trabajando · amarillo esperando material · rojo bloqueado (banda llena) · "
               "morado microparo · azul desplazándose. Cada cuadro avanza 5 s simulados.")
