"""Dashboard de estadísticas para el maestro."""
import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import actividad, sospechas, stats
from core.auth import require_login
from core.db import get_session
from models.schema import Asignacion

user = require_login(["maestro", "admin"])

st.title("📊 Estadísticas de uso")

if user["rol"] == "admin":
    materias_ids = None
else:
    with get_session() as s:
        materias_ids = list(s.scalars(select(Asignacion.materia_id).where(Asignacion.maestro_id == user["id"])))
    if not materias_ids:
        st.info("El administrador todavía no te ha asignado materias.")
        st.stop()

msgs, resp = stats.cargar(materias_ids)
if msgs.empty and resp.empty:
    st.info("Todavía no hay actividad de alumnos.")
    st.stop()

materias = sorted(set(msgs["materia"]) | set(resp["materia"]))
filtro = st.multiselect("Materias", materias, default=materias)
msgs = msgs[msgs["materia"].isin(filtro)]
resp = resp[resp["materia"].isin(filtro)]

buscar = st.text_input("🔍 Buscar alumno o tema", placeholder="Nombre del alumno o del tema…").strip()
if buscar:
    def _coincide(df):
        return (df["alumno"].astype(str).str.contains(buscar, case=False, regex=False)
                | df["tema"].astype(str).str.contains(buscar, case=False, regex=False))
    msgs, resp = msgs[_coincide(msgs)], resp[_coincide(resp)]
if msgs.empty and resp.empty:
    st.info("Sin resultados con esos filtros.")
    st.stop()

r = stats.resumen(msgs, resp)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Preguntas de alumnos", r["preguntas"])
m2.metric("Alumnos activos", r["alumnos_activos"])
m3.metric("Quizzes respondidos", r["quizzes_respondidos"])
m4.metric("% de aciertos", f"{r['pct_aciertos']:.1f}%")

st.divider()
a, b = st.columns(2)
with a:
    st.subheader("Preguntas por tema")
    df = stats.preguntas_por_tema(msgs)
    if df.empty:
        st.caption("Sin datos.")
    else:
        st.bar_chart(df.set_index("tema")["preguntas"])
with b:
    st.subheader("% de aciertos por tema")
    df = stats.aciertos_por_tema(resp)
    if df.empty:
        st.caption("Sin quizzes respondidos.")
    else:
        st.bar_chart(df.set_index("tema")["% aciertos"])
        st.dataframe(df, hide_index=True)

st.subheader("Uso por fecha")
df = stats.uso_por_fecha(msgs)
if df.empty:
    st.caption("Sin datos.")
else:
    st.line_chart(df["preguntas"])

c, d = st.columns(2)
with c:
    st.subheader("Alumnos más activos")
    st.dataframe(stats.alumnos_mas_activos(msgs), hide_index=True)
with d:
    st.subheader("Preguntas de quiz más falladas")
    st.dataframe(stats.preguntas_mas_falladas(resp), hide_index=True)

st.divider()
st.subheader("❓ Preguntas sin respuesta (falta material)")
sin_resp = stats.preguntas_sin_respuesta(materias_ids)
if sin_resp.empty:
    st.caption("El tutor ha podido responder todas las preguntas.")
else:
    st.dataframe(sin_resp, hide_index=True)
    st.caption("Son preguntas que el tutor no pudo contestar con el material subido. Conviene agregar ese contenido.")

e, f = st.columns(2)
with e:
    st.subheader("⏱️ Tiempo en la app")
    ids = sorted(set(msgs["alumno_id"]) | set(resp["alumno_id"]))
    nombres = {**dict(zip(msgs["alumno_id"], msgs["alumno"])), **dict(zip(resp["alumno_id"], resp["alumno"]))}
    segs = actividad.tiempo_por_alumno([int(i) for i in ids])
    df_t = pd.DataFrame([{"alumno": nombres[i], "minutos": round(segs.get(int(i), 0) / 60, 1)} for i in ids])
    st.dataframe(df_t.sort_values("minutos", ascending=False), hide_index=True)
    st.caption("Suma el tiempo entre acciones; las pausas de más de 5 minutos no cuentan.")
with f:
    st.subheader("🔎 Actividad a revisar")
    alertas = sospechas.cargar_y_evaluar(materias_ids)
    if buscar:
        alertas = alertas[alertas["alumno"].astype(str).str.contains(buscar, case=False, regex=False)]
    if alertas.empty:
        st.caption("Sin señales de actividad inusual.")
    else:
        st.dataframe(alertas, hide_index=True)
    st.caption("Son indicios, no prueba de que el alumno haya hecho trampa. Conviene revisarlos con él.")
