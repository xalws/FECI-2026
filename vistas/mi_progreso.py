import pandas as pd
import streamlit as st

from core import actividad, niveles, progreso
from core.auth import require_login

user = require_login(["alumno"])

st.title("Mi progreso")

segs = actividad.tiempo_por_alumno([user["id"]]).get(user["id"], 0)
filas = progreso.resumen_alumno(user["id"])

total_q = sum(f["intentos"] for f in filas)
total_ok = sum(f["aciertos"] for f in filas)
ejercicios = progreso.resumen_ejercicios(user["id"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Tiempo de estudio", f"{segs / 60:.0f} min")
c2.metric("Quizzes respondidos", total_q)
c3.metric("% de aciertos", f"{total_ok / total_q * 100:.0f}%" if total_q else "—")
c4.metric("Ejercicios (promedio)",
          f"{ejercicios['promedio']}/10 ({ejercicios['intentos']})" if ejercicios["intentos"] else "—")

def texto_tema(t: dict) -> str:
    base = f"{t['nombre']} — nivel {t['nivel']} · {t['nombre_nivel']}"
    if t["siguiente_xp"]:
        base += f" ({t['xp_efectivo']}/{t['siguiente_xp']} XP para el siguiente)"
    else:
        base += f" ({t['xp_efectivo']} XP, ¡nivel máximo!)"
    return base + (" ⚠️ precisión baja" if t["limitado"] else "")


st.subheader("Avance por unidad según la retícula")
materias = niveles.materias_disponibles()
if not materias:
    st.caption("Todavía no hay materias con retícula cargada.")
else:
    activas = niveles.materias_con_actividad(user["id"])
    orden = sorted(materias, key=lambda i: (i not in activas, materias[i]))  # primero donde ya estudió
    elegida = st.selectbox("Materia", orden, format_func=materias.get, key="progreso_materia")
    av = niveles.avance_materia(user["id"], elegida)
    m1, m2 = st.columns([1, 3])
    m1.metric("Nivel de la materia", f"Nivel {av['nivel']}", av["nombre_nivel"],
              delta_color="off", delta_arrow="off")
    m2.progress(av["porcentaje"] / 100, text=f"{av['porcentaje']}% de la materia · {av['xp']} XP en total")
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

st.subheader("Aciertos por tema")
st.bar_chart(df.set_index("tema")["porcentaje"])

repasar = df[df["nivel"] == "apoyo"]
if not repasar.empty:
    st.warning("Te conviene repasar: " + ", ".join(repasar["tema"]))
else:
    st.success("Ningún tema necesita refuerzo por ahora. ¡Sigue así!")

st.dataframe(
    df[["materia", "tema", "intentos", "aciertos", "porcentaje", "estado"]]
    .rename(columns={"porcentaje": "% aciertos"}),
    hide_index=True)
st.caption("Se cuentan tus últimos 10 quizzes de cada tema.")
