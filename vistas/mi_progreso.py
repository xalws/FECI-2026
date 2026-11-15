import pandas as pd
import streamlit as st

from core import actividad, material, niveles, progreso
from core.auth import require_login

user = require_login(["alumno"])

# Iconos SVG 
SVG = {
    "trending": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "layers": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "bulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
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
    </style>
    """,
    unsafe_allow_html=True,
)

titulo("trending", "Mi progreso", nivel=1)

segs = actividad.tiempo_por_alumno([user["id"]]).get(user["id"], 0)
filas = progreso.resumen_alumno(user["id"])

total_q = sum(f["intentos"] for f in filas)
total_ok = sum(f["aciertos"] for f in filas)
ejercicios = progreso.resumen_ejercicios(user["id"])
c1, c2, c3, c4 = st.columns(4)
c1.metric(":material/timer: Tiempo de estudio", f"{segs / 60:.0f} min")
c2.metric(":material/quiz: Quizzes respondidos", total_q)
c3.metric(":material/target: % de aciertos", f"{total_ok / total_q * 100:.0f}%" if total_q else "—")
c4.metric(":material/edit_note: Ejercicios (promedio)",
          f"{ejercicios['promedio']}/10 ({ejercicios['intentos']})" if ejercicios["intentos"] else "—")


def texto_tema(t: dict) -> str:
    base = f"{t['nombre']} — nivel {t['nivel']} · {t['nombre_nivel']}"
    if t["siguiente_xp"]:
        base += f" ({t['xp_efectivo']}/{t['siguiente_xp']} XP para el siguiente)"
    else:
        base += f" ({t['xp_efectivo']} XP, ¡nivel máximo!)"
    return base + (" :material/warning: precisión baja" if t["limitado"] else "")


st.write("")
titulo("layers", "Avance por unidad según la retícula")
materias = niveles.materias_disponibles()
if not materias:
    st.caption("Todavía no hay materias con retícula cargada.")
else:
    activas = niveles.materias_con_actividad(user["id"])
    orden = sorted(materias, key=lambda i: (i not in activas, materias[i]))  # primero donde ya estudió
    elegida = st.selectbox("Materia", orden, format_func=materias.get, key="progreso_materia")
    av = niveles.avance_materia(user["id"], elegida)
    with st.container(border=True):
        m1, m2 = st.columns([1, 3], vertical_alignment="center")
        m1.metric("Nivel de la materia", f"Nivel {av['nivel']}", av["nombre_nivel"],
                  delta_color="off", delta_arrow="off")
        m2.progress(av["porcentaje"] / 100, text=f"{av['porcentaje']}% de la materia · {av['xp']} XP en total")

    titulo("bulb", "Qué estudiar ahora", nivel=4)
    con_material = {c["tema_id"] for c in material.cobertura(elegida) if c["estado"] == "ok"}
    sugeridos = niveles.siguiente_recomendado(av, con_material)
    if not sugeridos:
        st.success("Ya dominas todos los temas que tienen material en esta materia. ¡Muy bien!",
                   icon=":material/check_circle:")
    for sug in sugeridos:
        with st.container(border=True):
            st.markdown(f"**{sug['tema']}** · {sug['unidad']}  \n{sug['razon']}")
    st.caption("Ve a «Chat de estudio», elige ese tema y practica con un examen o un ejercicio.")
    for u in av["unidades"]:
        with st.expander(f"{u['nombre']} — nivel {u['nivel']} ({u['nombre_nivel']}) · {u['porcentaje']}%",
                         expanded=u["porcentaje"] > 0):
            for t in u["temas"]:
                st.progress(t["porcentaje"] / 100, text=texto_tema(t))
    with st.expander("¿Cómo funcionan los niveles?"):
        st.markdown(
            "- Cada pregunta que aciertas suma **XP igual a su dificultad** (básica 1, intermedia 2, "
            "avanzada 3, experta 4). Los ejercicios calificados suman de 0 a 3 XP.\n"
            "- El nivel de cada tema depende de tus XP: **Principiante** (1), **Intermedio** (6), "
            "**Avanzado** (14) y **Experto** (24).\n"
            "- Con menos de 50% de aciertos (en 4 o más intentos) tu nivel no pasa de Principiante.\n"
            "- El nivel de una unidad o de la materia es el promedio de sus temas.")

if not filas:
    st.info("Aún no has respondido quizzes. Ve al chat de estudio y pulsa «Ponme un examen».")
    st.stop()

NIVELES = {"apoyo": "Por reforzar", "normal": "En camino", "avanzado": "Dominado"}
df = pd.DataFrame(filas)
df["estado"] = df["nivel"].map(NIVELES)

st.divider()
titulo("chart", "Aciertos por tema")
with st.container(border=True):
    st.bar_chart(df.set_index("tema")["porcentaje"])

repasar = df[df["nivel"] == "apoyo"]
if not repasar.empty:
    st.warning("Te conviene repasar: " + ", ".join(repasar["tema"]), icon=":material/warning:")
else:
    st.success("Ningún tema necesita refuerzo por ahora. ¡Sigue así!", icon=":material/check_circle:")

st.dataframe(
    df[["materia", "tema", "intentos", "aciertos", "porcentaje", "estado"]]
    .rename(columns={"porcentaje": "% aciertos"}),
    hide_index=True)
st.caption("Se cuentan tus últimos 10 quizzes de cada tema.")