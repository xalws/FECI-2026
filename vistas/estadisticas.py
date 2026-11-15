import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import actividad, niveles, sospechas, stats
from core.auth import require_login
from core.db import get_session
from models.schema import Asignacion

user = require_login(["maestro", "admin"])

# Iconos SVG 
SVG = {
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "x": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "layers": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
}


def titulo(icono: str, texto: str, nivel: int = 3):
    """Encabezado con icono SVG en línea."""
    size = 30 if nivel == 1 else 22
    st.markdown(
        f'<div class="tit"><svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{SVG[icono]}</svg><h{nivel}>{texto}</h{nivel}></div>',
        unsafe_allow_html=True,
    )


# Estilo
st.markdown(
    """
    <style>
    /* Encabezados con icono SVG */
    .tit { display: flex; align-items: center; gap: .6rem; margin: .6rem 0 .4rem; }
    .tit h1, .tit h2, .tit h3 { margin: 0; padding: 0; }
    .tit svg { flex-shrink: 0; }

    /* Tarjetas de métricas */
    div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 12px;
        padding: 14px 18px;
    }
    
    /* Botones redondeados */
    .stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

titulo("chart", "Estadísticas de uso", nivel=1)

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

# Filtros
materias = sorted(set(msgs["materia"]) | set(resp["materia"]))
with st.container(border=True):
    f1, f2 = st.columns([3, 2])
    filtro = f1.multiselect("Materias", materias, default=materias)
    buscar = f2.text_input("Buscar alumno o tema", placeholder="Nombre del alumno o del tema…",
                           icon=":material/search:").strip()
msgs = msgs[msgs["materia"].isin(filtro)]
resp = resp[resp["materia"].isin(filtro)]

if buscar:
    def _coincide(df):
        return (df["alumno"].astype(str).str.contains(buscar, case=False, regex=False)
                | df["tema"].astype(str).str.contains(buscar, case=False, regex=False))
    msgs, resp = msgs[_coincide(msgs)], resp[_coincide(resp)]
if msgs.empty and resp.empty:
    st.info("Sin resultados con esos filtros.")
    st.stop()

# Resumen
r = stats.resumen(msgs, resp)
m1, m2, m3, m4 = st.columns(4)
m1.metric(":material/chat: Preguntas de alumnos", r["preguntas"])
m2.metric(":material/group: Alumnos activos", r["alumnos_activos"])
m3.metric(":material/quiz: Quizzes respondidos", r["quizzes_respondidos"])
m4.metric(":material/target: % de aciertos", f"{r['pct_aciertos']:.1f}%")

st.divider()
a, b = st.columns(2)
with a:
    with st.container(border=True):
        titulo("message", "Preguntas por tema")
        df = stats.preguntas_por_tema(msgs)
        if df.empty:
            st.caption("Sin datos.")
        else:
            st.bar_chart(df.set_index("tema")["preguntas"])
with b:
    with st.container(border=True):
        titulo("check", "% de aciertos por tema")
        df = stats.aciertos_por_tema(resp)
        if df.empty:
            st.caption("Sin quizzes respondidos.")
        else:
            st.bar_chart(df.set_index("tema")["% aciertos"])
            st.dataframe(df, hide_index=True)

with st.container(border=True):
    titulo("calendar", "Uso por fecha")
    df = stats.uso_por_fecha(msgs)
    if df.empty:
        st.caption("Sin datos.")
    else:
        st.line_chart(df["preguntas"])

c, d = st.columns(2)
with c:
    with st.container(border=True):
        titulo("users", "Alumnos más activos")
        st.dataframe(stats.alumnos_mas_activos(msgs), hide_index=True)
with d:
    with st.container(border=True):
        titulo("x", "Preguntas de quiz más falladas")
        st.dataframe(stats.preguntas_mas_falladas(resp), hide_index=True)

st.divider()
titulo("help", "Preguntas sin respuesta (falta material)")
sin_resp = stats.preguntas_sin_respuesta(materias_ids)
if sin_resp.empty:
    st.caption("El tutor ha podido responder todas las preguntas.")
else:
    st.dataframe(sin_resp, hide_index=True)
    st.caption("Son preguntas que el tutor no pudo contestar con el material subido. Conviene agregar ese contenido.")

titulo("layers", "Avance por unidad (retícula)")
materias_con_datos = dict(zip(resp["materia_id"], resp["materia"]))
if not materias_con_datos:
    st.caption("Todavía no hay alumnos con quizzes en estas materias.")
else:
    mid = int(st.selectbox("Materia", list(materias_con_datos), format_func=materias_con_datos.get,
                           key="avance_materia"))
    de_la_materia = resp[resp["materia_id"] == mid]
    alumnos_materia = {int(i): n for i, n in zip(de_la_materia["alumno_id"], de_la_materia["alumno"])}
    st.dataframe(niveles.tabla_avance(mid, alumnos_materia), hide_index=True)
    st.caption("Nivel y % de avance de cada alumno por unidad. Se calcula con los XP de sus preguntas y ejercicios.")

e, f = st.columns(2)
with e:
    with st.container(border=True):
        titulo("clock", "Tiempo en la app")
        ids = sorted(set(msgs["alumno_id"]) | set(resp["alumno_id"]))
        nombres = {**dict(zip(msgs["alumno_id"], msgs["alumno"])), **dict(zip(resp["alumno_id"], resp["alumno"]))}
        segs = actividad.tiempo_por_alumno([int(i) for i in ids])
        df_t = pd.DataFrame([{"alumno": nombres[i], "minutos": round(segs.get(int(i), 0) / 60, 1)} for i in ids])
        st.dataframe(df_t.sort_values("minutos", ascending=False), hide_index=True)
        st.caption("Suma el tiempo entre acciones; las pausas de más de 5 minutos no cuentan.")
        resumen_csv = stats.resumen_por_alumno(msgs, resp, dict(zip(df_t["alumno"], df_t["minutos"])))
        st.download_button("Descargar resumen por alumno (CSV)",
                           resumen_csv.to_csv(index=False).encode("utf-8-sig"),
                           file_name="resumen_alumnos.csv", mime="text/csv",
                           icon=":material/download:")
with f:
    with st.container(border=True):
        titulo("search", "Actividad a revisar")
        alertas = sospechas.cargar_y_evaluar(materias_ids)
        if buscar:
            alertas = alertas[alertas["alumno"].astype(str).str.contains(buscar, case=False, regex=False)]
        if alertas.empty:
            st.caption("Sin señales de actividad inusual.")
        else:
            st.dataframe(alertas, hide_index=True)
        st.caption("Son indicios, no prueba de que el alumno haya hecho trampa. Conviene revisarlos con él.")