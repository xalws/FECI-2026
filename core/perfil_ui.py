"""Perfil de un alumno: lo que ve él mismo y lo que ven sus compañeros de clase (y su maestro)."""
import streamlit as st

from core import competencia
from core.estilo import (datos, encabezado, grafica_xp_semanal, lista, titulo, vitrina, zona_horaria)


def mostrar_perfil(p: dict, propio: bool = False, con_encabezado: bool = True) -> None:
    """Dibuja el perfil: título y XP, vitrina de logros, gráfica de XP por semana y temas dominados."""
    nivel, resumen = p["nivel"], p["resumen"]
    if con_encabezado:
        encabezado(p["nombre"], f"{nivel['nombre']} · {nivel['xp']} XP", "user", compacto=True,
                   chips=[("flame", f"Racha de {p['racha']} {'día' if p['racha'] == 1 else 'días'}"),
                          ("award", f"{resumen['medallas']} medallas · {resumen['oro']} de oro")])
    if nivel["siguiente"] is not None:
        st.progress(nivel["porcentaje"] / 100,
                    text=f"{nivel['xp']} / {nivel['siguiente']} XP para el siguiente título")
    else:
        st.caption("Ya tiene el título más alto.")

    datos([{"icono": "zap", "etiqueta": "XP de esta semana", "valor": p["xp_semana"], "detalle": "se reinicia el lunes",
            "tono": "indigo"},
           {"icono": "flame", "etiqueta": "Racha", "valor": f"{p['racha']} {'día' if p['racha'] == 1 else 'días'}",
            "detalle": "estudiando seguidos", "tono": "ambar"},
           {"icono": "clock", "etiqueta": "Estudio esta semana", "valor": f"{p['minutos_semana']} min",
            "detalle": "tiempo activo en la app", "tono": "cielo"},
           {"icono": "award", "etiqueta": "Logros", "valor": f"{resumen['logros']}",
            "detalle": f"{resumen['medallas']} medallas en total", "tono": "violeta"}])

    titulo("star", "Logros destacados")
    vitrina(p["vitrina"], "Todavía no tiene logros." if not propio else
            "Aún no tienes logros: responde preguntas, resuelve ejercicios y estudia a diario para conseguirlos.")

    titulo("trending", "XP ganados por semana")
    with st.container(border=True):
        grafica_xp_semanal(competencia.solo_semanas(p))

    titulo("award", "Temas que domina")
    if p["temas_dominados"]:
        lista([{"icono": "award", "titulo": t["tema"], "sub": t["materia"], "tono": "verde" if t["nivel"] >= 4 else "indigo",
                "texto": f"Nivel {t['nombre_nivel']}"} for t in p["temas_dominados"]])
    else:
        st.caption("Aún no llega a nivel Avanzado en ningún tema.")


@st.dialog("Perfil de tu compañero", width="large")
def dialogo_perfil(viewer_id: int, alumno_id: int) -> None:
    """Ventana con el perfil de otro alumno (solo si comparten clase, o si quien mira es su maestro o el admin)."""
    p = competencia.perfil_publico(viewer_id, alumno_id, zona_horaria())
    if p is None:
        st.error("No puedes ver este perfil.", icon=":material/lock:")
        return
    mostrar_perfil(p, propio=False)
