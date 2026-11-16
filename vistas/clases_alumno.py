"""Mis clases: el alumno se une con un código, ve sus clases y los avisos de sus maestros."""
import streamlit as st

from core import clases
from core.auth import require_login
from core.estilo import datos, encabezado, fecha_local, insignias, titulo

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
