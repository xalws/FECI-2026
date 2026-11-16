"""Presentación de las tareas del alumno (la usan «Mis clases» y la pantalla de Estudio)."""
from datetime import datetime, timezone

import streamlit as st

from core import tareas
from core.estilo import fecha_local, insignias, titulo, zona_horaria

# estado -> (texto, tono, ícono)
ETIQUETA_ESTADO = {"hecha": ("Hecha", "verde", "check"), "pronto": ("Por vencer", "ambar", "clock"),
                   "pendiente": ("Pendiente", "cielo", "clock"), "vencida": ("Vencida", "rojo", "x")}


def _avance_texto(t: dict) -> str:
    if t["tipo"] == "nivel":
        return f"Nivel actual {t['avance']} de {t['meta']}"
    return f"{t['avance']} de {t['meta']}"


def tarjeta(t: dict) -> None:
    """Una tarea con su avance, su plazo y su estado."""
    ahora = datetime.now(timezone.utc)
    texto, tono, icono = ETIQUETA_ESTADO[t["estado"]]
    with st.container(border=True):
        titulo("clipboard", t["descripcion"], nivel=5)
        plazo = tareas.texto_plazo(t["fecha_limite"], ahora, zona_horaria())
        insignias((texto, tono, icono), (f"{plazo} · {fecha_local(t['fecha_limite']):%d/%m}", "indigo", "calendar"))
        st.markdown(f"**{t['tema']}** · {t['clase']}")
        if t["instrucciones"]:
            st.caption(t["instrucciones"])
        st.progress(min(1.0, t["avance"] / t["meta"]), text=_avance_texto(t))


def resumen_estudio(alumno_id: int, limite: int = 3) -> None:
    """Las tareas que faltan, arriba de la pantalla de Estudio (no muestra nada si no hay)."""
    pendientes = tareas.pendientes(alumno_id)
    if not pendientes:
        return
    ahora = datetime.now(timezone.utc)
    zona = zona_horaria()
    with st.container(border=True, key="tareas_pendientes"):
        titulo("clipboard", f"Tareas pendientes ({len(pendientes)})", nivel=4)
        for t in pendientes[:limite]:
            urgente = t["estado"] == "pronto"
            st.markdown(f"**{t['descripcion']}** · {t['tema']} · {t['clase']}")
            st.caption(f"{':material/schedule: ' if urgente else ''}{tareas.texto_plazo(t['fecha_limite'], ahora, zona)} · "
                       f"{_avance_texto(t)}")
        if len(pendientes) > limite:
            st.caption(f"y {len(pendientes) - limite} más…")
        st.page_link("vistas/clases_alumno.py", label="Ver todas mis tareas", icon=":material/groups:")
