import pandas as pd
import streamlit as st

from core import actividad, logros, material, niveles, progreso, tareas
from core.auth import require_login
from core.estilo import (TONOS, anillo, calendario_actividad, datos, encabezado, grafica_barras, lista, titulo,
                         vitrina, zona_horaria)

user = require_login(["alumno"])


def duracion(segundos: float) -> str:
    minutos = round(segundos / 60)
    return f"{minutos} min" if minutos < 60 else f"{minutos // 60} h {minutos % 60:02d} min"


def plural(n: int, singular: str, plural_: str) -> str:
    return f"{n} {singular if n == 1 else plural_}"


segs = actividad.tiempo_por_alumno([user["id"]]).get(user["id"], 0)
racha = actividad.racha_dias(user["id"], zona_horaria())
filas = progreso.resumen_alumno(user["id"])
total_q = sum(f["intentos"] for f in filas)
total_ok = sum(f["aciertos"] for f in filas)
ejercicios = progreso.resumen_ejercicios(user["id"])

encabezado("Mi progreso", "Tu avance por materia, unidad y tema, y lo que te conviene estudiar ahora.", "trending",
           chips=[("flame", f"Racha de {plural(racha, 'día seguido', 'días seguidos')}" if racha
                   else "Estudia hoy para empezar tu racha")])

datos([
    {"icono": "clock", "etiqueta": "Tiempo de estudio", "valor": duracion(segs),
     "detalle": "tiempo activo en la app", "tono": "indigo"},
    {"icono": "help", "etiqueta": "Quizzes respondidos", "valor": total_q,
     "detalle": plural(total_ok, "correcto", "correctos"), "tono": "violeta"},
    {"icono": "target", "etiqueta": "Aciertos", "valor": f"{total_ok / total_q * 100:.0f}%" if total_q else "—",
     "detalle": "en tus quizzes recientes", "tono": "verde"},
    {"icono": "bulb", "etiqueta": "Promedio en ejercicios",
     "valor": f"{ejercicios['promedio']}/10" if ejercicios["intentos"] else "—",
     "detalle": (plural(ejercicios["intentos"], "ejercicio calificado", "ejercicios calificados")
                 if ejercicios["intentos"] else "aún sin ejercicios"), "tono": "cielo"},
])


# Meta diaria y logros
zona = zona_horaria()
dl = logros.datos_alumno(user["id"], zona)
lista_logros = logros.evaluar(dl)
logros.revisar_nuevos(user["id"], zona, dl)


def guardar_meta() -> None:
    logros.guardar_meta(user["id"], st.session_state["meta_diaria"])


st.write("")
titulo("target", "Tu meta diaria")
col_meta, col_cal = st.columns([1, 1.3], gap="medium")
hoy_min, meta_min = dl["minutos_hoy"], dl["meta"]
with col_meta:
    anillo(min(100, hoy_min / meta_min * 100), f"{round(hoy_min)} de {meta_min} min hoy",
           "¡Meta cumplida, muy bien!" if hoy_min >= meta_min else f"Te faltan {max(1, round(meta_min - hoy_min))} min para tu meta.",
           etiqueta=f"{dl['dias_meta']} {'día' if dl['dias_meta'] == 1 else 'días'} con la meta cumplida",
           tono="verde" if hoy_min >= meta_min else "indigo")
    st.session_state["meta_diaria"] = meta_min  # el valor guardado manda; el cambio se guarda al elegir otro
    st.selectbox("Mi meta de estudio al día", logros.METAS_MIN, key="meta_diaria", on_change=guardar_meta,
                 format_func=lambda m: f"{m} minutos")
with col_cal:
    calendario_actividad(logros.calendario(dl["minutos"], dl["hoy"], futuras=2), meta_min, dl["hoy"],
                         tareas.por_dia(user["id"], zona))

resumen_logros = logros.resumen(lista_logros)
titulo("award", f"Tus logros · {resumen_logros['logros']} de {len(lista_logros)} ({resumen_logros['oro']} de oro)")
vitrina(logros.elegir_vitrina(lista_logros, logros.vitrina_de(user["id"])),
        "Aún no tienes logros: responde preguntas, resuelve ejercicios y estudia a diario para conseguirlos.")
st.page_link("vistas/mi_perfil.py", label="Ver todos mis logros y elegir cuáles mostrar", icon=":material/badge:")


def texto_tema(t: dict) -> str:
    base = f"{t['nombre']} — nivel {t['nivel']} · {t['nombre_nivel']}"
    if t["siguiente_xp"]:
        base += f" ({t['xp_efectivo']}/{t['siguiente_xp']} XP para el siguiente)"
    else:
        base += f" ({t['xp_efectivo']} XP, ¡nivel máximo!)"
    return base + (" :material/warning: precisión baja" if t["limitado"] else "")


def icono_unidad(porcentaje: float) -> str:
    if porcentaje >= 100:
        return ":material/check_circle:"
    return ":material/progress_activity:" if porcentaje > 0 else ":material/radio_button_unchecked:"


st.write("")
titulo("layers", "Avance por materia según la retícula")
materias = niveles.materias_disponibles()
if not materias:
    st.caption("Todavía no hay materias con retícula cargada.")
else:
    activas = niveles.materias_con_actividad(user["id"])
    orden = sorted(materias, key=lambda i: (i not in activas, materias[i]))  # primero donde ya estudió
    elegida = st.selectbox("Materia", orden, format_func=materias.get, key="progreso_materia")
    av = niveles.avance_materia(user["id"], elegida)
    con_material = {c["tema_id"] for c in material.cobertura(elegida) if c["estado"] == "ok"}
    sugeridos = niveles.siguiente_recomendado(av, con_material)

    col_avance, col_sugerencias = st.columns([1, 1.35], gap="medium")
    with col_avance:
        anillo(av["porcentaje"], materias[elegida].split(" · ")[0],
               f"{av['xp']} XP en total · {plural(len(av['unidades']), 'unidad', 'unidades')}",
               etiqueta=f"Nivel {av['nivel']} · {av['nombre_nivel']}")
        with st.container(border=True):
            for u in av["unidades"]:
                st.progress(u["porcentaje"] / 100, text=f"{u['nombre']} · {u['porcentaje']}%")
    with col_sugerencias:
        titulo("bulb", "Qué estudiar ahora", nivel=4)
        if sugeridos:
            lista([{"icono": "target", "titulo": s["tema"], "sub": s["unidad"], "texto": s["razon"],
                    "tono": ["indigo", "violeta", "cielo"][i % 3]} for i, s in enumerate(sugeridos)])
            st.caption("Ve a «Estudio», elige ese tema y practica con un examen o un ejercicio.")
        else:
            st.success("Ya dominas todos los temas que tienen material en esta materia. ¡Muy bien!",
                       icon=":material/check_circle:")

    titulo("layers", "Detalle por tema", nivel=4)
    for u in av["unidades"]:
        with st.expander(f"{u['nombre']} — nivel {u['nivel']} ({u['nombre_nivel']}) · {u['porcentaje']}%",
                         expanded=u["porcentaje"] > 0, icon=icono_unidad(u["porcentaje"])):
            for t in u["temas"]:
                st.progress(t["porcentaje"] / 100, text=texto_tema(t))
    with st.expander("¿Cómo funcionan los niveles?", icon=":material/help:"):
        st.markdown(
            "- Cada pregunta que aciertas suma **XP igual a su dificultad** (básica 1, intermedia 2, "
            "avanzada 3, experta 4). Los ejercicios calificados suman de 0 a 3 XP.\n"
            "- El nivel de cada tema depende de tus XP: **Principiante** (1), **Intermedio** (6), "
            "**Avanzado** (14) y **Experto** (24).\n"
            "- Con menos de 50% de aciertos (en 4 o más intentos) tu nivel no pasa de Principiante.\n"
            "- El nivel de una unidad o de la materia es el promedio de sus temas.")

if not filas:
    st.info("Aún no has respondido quizzes. Ve a «Estudio», elige un tema y abre la pestaña «Examen».",
            icon=":material/info:")
    st.stop()

ESTADOS = {"apoyo": "Por reforzar", "normal": "En camino", "avanzado": "Dominado"}
df = pd.DataFrame(filas)
df["estado"] = df["nivel"].map(ESTADOS)

st.write("")
titulo("chart", "Aciertos por tema")
with st.container(border=True):
    grafica_barras(df, "tema", "porcentaje", "% de aciertos", maximo=100, color_por="estado",
                   colores={"Por reforzar": TONOS["ambar"][0], "En camino": TONOS["indigo"][0],
                            "Dominado": TONOS["verde"][0]})

repasar = df[df["nivel"] == "apoyo"]
if not repasar.empty:
    st.warning("Te conviene repasar: " + ", ".join(repasar["tema"]), icon=":material/warning:")
else:
    st.success("Ningún tema necesita refuerzo por ahora. ¡Sigue así!", icon=":material/check_circle:")

st.dataframe(
    df[["materia", "tema", "intentos", "aciertos", "porcentaje", "estado"]],
    hide_index=True, width="stretch",
    column_config={
        "materia": "Materia", "tema": "Tema", "intentos": "Intentos", "aciertos": "Aciertos",
        "porcentaje": st.column_config.ProgressColumn("% de aciertos", min_value=0, max_value=100, format="%d%%"),
        "estado": "Estado"})
st.caption("Se cuentan tus últimos 10 quizzes de cada tema.")
