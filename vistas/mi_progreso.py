import pandas as pd
import streamlit as st

from core import actividad, progreso
from core.auth import require_login

user = require_login(["alumno"])

st.title("Mi progreso")

segs = actividad.tiempo_por_alumno([user["id"]]).get(user["id"], 0)
filas = progreso.resumen_alumno(user["id"])

total_q = sum(f["intentos"] for f in filas)
total_ok = sum(f["aciertos"] for f in filas)
c1, c2, c3 = st.columns(3)
c1.metric("Tiempo de estudio", f"{segs / 60:.0f} min")
c2.metric("Quizzes respondidos", total_q)
c3.metric("% de aciertos", f"{total_ok / total_q * 100:.0f}%" if total_q else "—")

if not filas:
    st.info("Aún no has respondido quizzes. Ve al chat de estudio y pulsa «Ponme un quiz».")
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
