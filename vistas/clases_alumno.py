"""Mis clases: el alumno se une con un código, ve sus clases y los avisos de sus maestros."""
import streamlit as st

from core import clases, competencia, tareas
from core.auth import require_login
from core.estilo import datos, encabezado, fecha_local, fila_ranking, insignias, posicion_html, titulo, zona_horaria
from core.perfil_ui import dialogo_perfil
from core.tareas_ui import tarjeta as tarjeta_tarea

user = require_login(["alumno"])
ss = st.session_state

MAX_FALLOS = 5  # intentos de código incorrectos por sesión (evita adivinar códigos a fuerza bruta)

mis = clases.clases_del_alumno(user["id"])
activas = [c for c in mis if c["estado"] == clases.ACTIVO]
pendientes = [c for c in mis if c["estado"] == clases.PENDIENTE]
encabezado("Mis clases", "Únete a la clase de tu maestro con su código y mira sus avisos.", "users",
           chips=[("users", f"{len(activas)} {'clase' if len(activas) == 1 else 'clases'}")]
           + ([("clock", f"{len(pendientes)} por aprobar")] if pendientes else []))

aviso = ss.pop("aviso_mis_clases", None)
if aviso:
    st.toast(aviso[0], icon=":material/check_circle:" if aviso[1] else ":material/error:")

# ---------------------------------------------------------------------------------------------------------------
# Unirse con un código
# ---------------------------------------------------------------------------------------------------------------
with st.container(border=True, key="tarjeta_unirse"):
    titulo("key", "Unirme con un código", nivel=4)
    st.caption("Tu maestro te da un código de 6 letras y números (por ejemplo «K7M2QX»).")
    with st.form("form_unirse", clear_on_submit=True, border=False):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        codigo = c1.text_input("Código de la clase", placeholder="K7M2QX", max_chars=12)
        if c2.form_submit_button("Unirme", type="primary", icon=":material/login:", width="stretch"):
            if ss.get("fallos_codigo", 0) >= MAX_FALLOS:
                st.error("Demasiados intentos con códigos incorrectos. Recarga la página para intentar de nuevo.",
                         icon=":material/lock:")
            else:
                ok, msg = clases.unirse(user["id"], codigo)
                if not ok and "No encontré" in msg:
                    ss["fallos_codigo"] = ss.get("fallos_codigo", 0) + 1
                ss["aviso_mis_clases"] = (msg, ok)
                st.rerun()

if not mis:
    st.info("Todavía no estás en ninguna clase. Pídele el código a tu maestro y escríbelo arriba.", icon=":material/group_add:")
    st.stop()

# ---------------------------------------------------------------------------------------------------------------
# Mis clases
# ---------------------------------------------------------------------------------------------------------------
datos([{"icono": "users", "etiqueta": "Mis clases", "valor": len(activas), "detalle": "donde ya estoy aceptado",
        "tono": "indigo"},
       {"icono": "clock", "etiqueta": "Por aprobar", "valor": len(pendientes), "detalle": "esperando a tu maestro",
        "tono": "ambar" if pendientes else "verde"}])

# ---------------------------------------------------------------------------------------------------------------
# Tareas de mis maestros
# ---------------------------------------------------------------------------------------------------------------
if activas:
    todas = tareas.tareas_del_alumno(user["id"])
    por_hacer = [t for t in todas if t["estado"] in ("pendiente", "pronto")]
    cerradas = [t for t in todas if t["estado"] in ("vencida", "hecha")]
    titulo("clipboard", f"Mis tareas ({len(por_hacer)} por hacer)")
    if not todas:
        st.caption("Tus maestros todavía no han asignado tareas.")
    elif not por_hacer:
        st.success("No tienes tareas pendientes. ¡Bien hecho!", icon=":material/check_circle:")
    for t in por_hacer:
        tarjeta_tarea(t)
    if cerradas:
        with st.expander(f"Hechas y vencidas ({len(cerradas)})"):
            for t in cerradas:
                tarjeta_tarea(t)
    st.caption("Las tareas se cumplen solas con lo que haces en «Estudio»: no hay nada que entregar.")

titulo("users", "Mis grupos")
for c in mis:
    with st.container(border=True):
        f1, f2 = st.columns([4, 1], vertical_alignment="center")
        with f1:
            titulo("book", c["nombre"], nivel=4)
            insignias((c["materia"], "indigo", "book"), (f"Maestro: {c['maestro']}", "violeta", "user"),
                      (("Aceptado", "verde", "check") if c["estado"] == clases.ACTIVO else ("Esperando aprobación", "ambar", "clock")),
                      *([] if c["activa"] else [("Clase desactivada", "rojo", "x")]))
        if f2.button("Salir" if c["estado"] == clases.ACTIVO else "Cancelar", key=f"salir_{c['id']}",
                     icon=":material/logout:", width="stretch"):
            ss["confirmar_salir"] = c["id"]
        if ss.get("confirmar_salir") == c["id"]:
            st.warning(f"¿Salir de «{c['nombre']}»? Tu progreso no se borra; para volver necesitarás el código.",
                       icon=":material/warning:")
            b1, b2 = st.columns(2)
            if b1.button("Sí, salir", key=f"si_salir_{c['id']}", type="primary", width="stretch"):
                ss.pop("confirmar_salir", None)
                ok, msg = clases.salir(user["id"], c["id"])
                ss["aviso_mis_clases"] = (msg, ok)
                st.rerun()
            if b2.button("No", key=f"no_salir_{c['id']}", width="stretch"):
                ss.pop("confirmar_salir", None)
                st.rerun()

# ---------------------------------------------------------------------------------------------------------------
# Ranking de la clase y perfil de mis compañeros
# ---------------------------------------------------------------------------------------------------------------
if activas:
    titulo("trending", "Ranking de la clase")
    st.caption("Se compara el esfuerzo: los XP que gana cada quien al responder preguntas y resolver ejercicios. "
               "Abre el perfil de un compañero para ver sus logros y su avance.")
    c1, c2 = st.columns([2, 1])
    opciones = {c["id"]: f"{c['nombre']} · {c['materia']}" for c in activas}
    clase_rank = c1.selectbox("Clase", list(opciones), format_func=opciones.get, key="ranking_clase")
    periodo = c2.radio("Periodo", ["Total", "Esta semana"], horizontal=True, key="ranking_periodo")
    filas = competencia.ranking(clase_rank, zona_horaria(), "semana" if periodo == "Esta semana" else "total")
    mia = next((f for f in filas if f["alumno_id"] == user["id"]), None)
    if mia:
        st.success(f"Vas en el lugar {mia['posicion']} de {len(filas)} con {mia['xp']} XP"
                   + (" esta semana." if periodo == "Esta semana" else "."), icon=":material/emoji_events:")
    for f in filas:
        yo = f["alumno_id"] == user["id"]
        k1, k2, k3 = st.columns([0.6, 5, 1.6], vertical_alignment="center")
        k1.markdown(posicion_html(f["posicion"]), unsafe_allow_html=True)
        k2.markdown(fila_ranking(f["nombre"], f["titulo"] or "", f["xp"], yo), unsafe_allow_html=True)
        if k3.button("Mi perfil" if yo else "Ver perfil", key=f"ver_{clase_rank}_{f['alumno_id']}", icon=":material/badge:",
                     width="stretch"):
            dialogo_perfil(user["id"], f["alumno_id"])

# ---------------------------------------------------------------------------------------------------------------
# Avisos de mis maestros
# ---------------------------------------------------------------------------------------------------------------
titulo("bulb", "Avisos de tus maestros")
avisos = clases.avisos_para_alumno(user["id"], dias=60, limite=10)
if not avisos:
    st.caption("No hay avisos recientes.")
for a in avisos:
    with st.container(border=True):
        st.markdown(a["texto"])
        st.caption(f"{a['autor']} · {a['clase']} · {fecha_local(a['fecha']):%d/%m/%Y %H:%M}")
