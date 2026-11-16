from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import select

from core import actividad, clases, niveles, sospechas, stats
from core.auth import require_login
from core.db import get_session
from core.estilo import datos, encabezado, grafica_barras, grafica_fechas, lista, titulo, zona_horaria
from models.schema import Asignacion

user = require_login(["maestro", "admin"])

# Los íconos, títulos y estilos vienen de core/estilo.py (compartidos por todas las pantallas)

if user["rol"] == "admin":
    materias_ids = None
else:
    with get_session() as s:
        materias_ids = list(s.scalars(select(Asignacion.materia_id).where(Asignacion.maestro_id == user["id"])))
if materias_ids is None:
    alcance = "Todas las materias"
else:
    alcance = f"{len(materias_ids)} {'materia asignada' if len(materias_ids) == 1 else 'materias asignadas'}"
encabezado("Estadísticas de uso", "Cómo usan tus alumnos el tutor: preguntas, aciertos, avance y tiempo de estudio.",
           "chart", chips=[("layers", alcance)])
if materias_ids is not None and not materias_ids:
    st.info("El administrador todavía no te ha asignado materias.", icon=":material/info:")
    st.stop()

msgs, resp = stats.cargar(materias_ids)
if msgs.empty and resp.empty:
    st.info("Todavía no hay actividad de alumnos.")
    st.stop()

# Filtros
materias = sorted(set(msgs["materia"]) | set(resp["materia"]))
mis_clases = clases.clases_del_maestro(user["id"])
with st.container(border=True):
    f1, f2, f3 = st.columns([3, 2, 2])
    filtro = f1.multiselect("Materias", materias, default=materias)
    buscar = f2.text_input("Buscar alumno o tema", placeholder="Nombre del alumno o del tema…",
                           icon=":material/search:").strip()
    opciones_clase = {0: "Todos los alumnos", **{c["id"]: f"{c['nombre']} · {c['materia']}" for c in mis_clases}}
    clase_id = f3.selectbox("Clase", list(opciones_clase), format_func=opciones_clase.get, key="filtro_clase",
                            help="Muestra solo a los alumnos de esa clase y su materia.")
msgs = msgs[msgs["materia"].isin(filtro)]
resp = resp[resp["materia"].isin(filtro)]
clase = next((c for c in mis_clases if c["id"] == clase_id), None)
ids_clase = None
if clase:
    ids_clase = set(clases.alumnos_ids(clase["id"]))
    msgs = msgs[msgs["alumno_id"].isin(ids_clase) & (msgs["materia_id"] == clase["materia_id"])]
    resp = resp[resp["alumno_id"].isin(ids_clase) & (resp["materia_id"] == clase["materia_id"])]

if buscar:
    def _coincide(df):
        return (df["alumno"].astype(str).str.contains(buscar, case=False, regex=False)
                | df["tema"].astype(str).str.contains(buscar, case=False, regex=False))
    msgs, resp = msgs[_coincide(msgs)], resp[_coincide(resp)]
if msgs.empty and resp.empty:
    st.info("Esta clase todavía no tiene actividad." if clase else "Sin resultados con esos filtros.")
    st.stop()

# Resumen
r = stats.resumen(msgs, resp)
datos([{"icono": "message", "etiqueta": "Preguntas de alumnos", "valor": r["preguntas"],
        "detalle": "hechas al tutor", "tono": "indigo"},
       {"icono": "users", "etiqueta": "Alumnos activos", "valor": r["alumnos_activos"],
        "detalle": "con preguntas o quizzes", "tono": "violeta"},
       {"icono": "help", "etiqueta": "Quizzes respondidos", "valor": r["quizzes_respondidos"],
        "detalle": "en exámenes y repasos", "tono": "cielo"},
       {"icono": "target", "etiqueta": "Aciertos", "valor": f"{r['pct_aciertos']:.1f}%",
        "detalle": "promedio de los quizzes", "tono": "verde"}])

# Preguntas que el tutor no pudo responder: si varios alumnos coinciden en un tema, falta material ahí
sin_resp = stats.preguntas_sin_respuesta(materias_ids, alumnos_ids=ids_clase)
sin_resp = sin_resp[sin_resp["materia"].isin(filtro)].reset_index(drop=True)
if clase:
    sin_resp = sin_resp[sin_resp["materia"] == clase["materia"]].reset_index(drop=True)
if buscar:
    sin_resp = sin_resp[sin_resp["alumno"].astype(str).str.contains(buscar, case=False, regex=False)
                        | sin_resp["tema"].astype(str).str.contains(buscar, case=False, regex=False)]
faltantes = stats.material_faltante(sin_resp)
if not faltantes.empty:
    titulo("bulb", f"Falta material en {len(faltantes)} {'tema' if len(faltantes) == 1 else 'temas'}")
    lista([{"icono": "help", "titulo": f["tema"], "sub": f["materia"], "tono": "ambar",
            "texto": f"{f['alumnos']} alumnos preguntaron lo que el material no cubre ({f['preguntas']} preguntas). "
                     f"Por ejemplo: «{f['ejemplo'][:140]}»"}
           for _, f in faltantes.head(5).iterrows()])
    st.caption("Sube PDFs sobre estos temas en «Material de la IA» y el tutor podrá contestar a tus alumnos.")

a, b = st.columns(2)
with a:
    with st.container(border=True):
        titulo("message", "Preguntas por tema")
        df = stats.preguntas_por_tema(msgs)
        if df.empty:
            st.caption("Sin datos.")
        else:
            grafica_barras(df, "tema", "preguntas", "Preguntas")
with b:
    with st.container(border=True):
        titulo("check", "% de aciertos por tema")
        df = stats.aciertos_por_tema(resp)
        if df.empty:
            st.caption("Sin quizzes respondidos.")
        else:
            grafica_barras(df, "tema", "% aciertos", "% de aciertos", maximo=100)
            st.dataframe(df, hide_index=True, column_config={
                "tema": st.column_config.TextColumn("Tema", width="medium"),
                "intentos": st.column_config.NumberColumn("Intentos", width="small"),
                "% aciertos": st.column_config.ProgressColumn("% de aciertos", min_value=0, max_value=100,
                                                              format="%.0f%%", width="small")})

with st.container(border=True):
    titulo("calendar", "Uso por fecha")
    # los días se cuentan en la hora local del maestro, no en UTC
    df = stats.uso_por_fecha(msgs.assign(fecha=msgs["fecha"].dt.tz_convert(zona_horaria())))
    if df.empty:
        st.caption("Sin datos.")
    else:
        por_dia = df.reset_index()
        por_dia.columns = ["fecha", "preguntas"]
        por_dia["fecha"] = pd.to_datetime(por_dia["fecha"])
        # los días sin preguntas cuentan como 0 (si no, la línea une días lejanos)
        por_dia = por_dia.set_index("fecha").asfreq("D", fill_value=0).reset_index()
        grafica_fechas(por_dia, "fecha", "preguntas", "Preguntas")

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
if sin_resp.empty:
    st.caption("El tutor ha podido responder todas las preguntas.")
else:
    if "fecha" in sin_resp:
        sin_resp["fecha"] = pd.to_datetime(sin_resp["fecha"], utc=True).dt.tz_convert(zona_horaria())
    st.dataframe(sin_resp, hide_index=True,
                 column_config={"fecha": st.column_config.DatetimeColumn("fecha", format="DD/MM/YYYY HH:mm")})
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
    avance = niveles.tabla_avance(mid, alumnos_materia)
    st.dataframe(avance, hide_index=True)
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
        d1, d2 = st.columns(2)
        d1.download_button("Resumen (CSV)", resumen_csv.to_csv(index=False).encode("utf-8-sig"),
                           file_name="resumen_alumnos.csv", mime="text/csv", icon=":material/download:",
                           width="stretch")
        hojas = {"Resumen por alumno": resumen_csv, "Tiempo en la app": df_t,
                 "Aciertos por tema": stats.aciertos_por_tema(resp),
                 "Alumnos más activos": stats.alumnos_mas_activos(msgs),
                 "Preguntas más falladas": stats.preguntas_mas_falladas(resp),
                 "Preguntas sin respuesta": sin_resp, "Material faltante": faltantes}
        if materias_con_datos:
            hojas[f"Avance {materias_con_datos[mid]}"] = avance
        d2.download_button("Reporte completo (Excel)", stats.exportar_excel(hojas),
                           file_name=f"reporte_{datetime.now(zona_horaria()):%Y-%m-%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/table_view:", type="primary", width="stretch")
        st.caption("El reporte respeta las materias y la búsqueda que elegiste arriba.")
with f:
    with st.container(border=True):
        titulo("search", "Actividad a revisar")
        alertas = sospechas.cargar_y_evaluar(materias_ids)
        if clase:
            alertas = alertas[alertas["alumno"].isin(set(msgs["alumno"]) | set(resp["alumno"]))]
        if buscar:
            alertas = alertas[alertas["alumno"].astype(str).str.contains(buscar, case=False, regex=False)]
        if alertas.empty:
            st.caption("Sin señales de actividad inusual.")
        else:
            st.dataframe(alertas, hide_index=True)
        st.caption("Son indicios, no prueba de que el alumno haya hecho trampa. Conviene revisarlos con él.")