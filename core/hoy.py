"""Lo que el alumno tiene pendiente hoy: tareas, tarjetas de repaso, racha y reto de la semana.

Alimenta las insignias del menú («Mis clases (2)», «Repaso (3)») y el panel «Tu día» arriba de Estudio.
"""
from datetime import datetime, timezone

import streamlit as st

from core import logros, repaso, retos, tareas
from core.estilo import insignias, titulo, zona_horaria


def menu_pendientes(user: dict) -> dict[str, int]:
    """{url de la página: número que se muestra junto a su nombre en el menú}."""
    return {"mis-clases": len(tareas.pendientes(user["id"])), "repaso": repaso.contar_pendientes(user["id"])}


def racha_en_riesgo(racha: int, minutos_hoy: float, minimo: int = 2) -> bool:
    """True si hay una racha que cuidar (al menos `minimo` días) y hoy todavía no se ha estudiado nada."""
    return racha >= minimo and minutos_hoy <= 0


def panel_estudio(alumno_id: int) -> None:
    """Panel «Tu día» (racha en riesgo, tarjetas de repaso y reto de la semana); no muestra nada si no hay nada que decir."""
    zona = zona_horaria()
    dl = logros.datos_alumno(alumno_id, zona)
    avisos = []
    if racha_en_riesgo(dl["racha"], dl["minutos_hoy"]):
        avisos.append(("flame", f"Tu racha de {dl['racha']} días está en riesgo: hoy todavía no has estudiado. "
                                f"Con {dl['meta']} minutos la salvas.", "ambar"))
    n_repaso = repaso.contar_pendientes(alumno_id)
    if n_repaso:
        avisos.append(("refresh", f"Tienes {n_repaso} {'tarjeta' if n_repaso == 1 else 'tarjetas'} de repaso para hoy.", "cielo"))
    reto = retos.reto_de_semana(dl["hoy"])
    avance = retos.avance_semana(dl, dl["hoy"])
    if avance < reto["meta"]:
        avisos.append(("target", f"Reto de la semana: {reto['texto'].lower()} ({avance} de {reto['meta']}).", "indigo"))
    if not avisos:
        return
    with st.container(border=True, key="tu_dia"):
        titulo("sparkles", "Tu día", nivel=4)
        for icono, texto, tono in avisos:
            insignias((texto, tono, icono))
        c1, c2 = st.columns(2)
        if n_repaso:
            c1.page_link("vistas/repaso.py", label="Ir a repasar", icon=":material/refresh:")
        c2.page_link("vistas/clases_alumno.py", label="Ver el reto y la liga", icon=":material/emoji_events:")
