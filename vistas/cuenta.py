"""Mi cuenta: cambiar la propia contraseña y, para el administrador, restablecer la de otros usuarios."""
import streamlit as st
from sqlalchemy import select

from core import cuenta, voz
from core.auth import require_login
from core.db import get_session
from core.estilo import encabezado, lista, titulo
from models.schema import Usuario

user = require_login()
ROLES = {"alumno": "Alumno", "maestro": "Maestro", "admin": "Administrador"}

encabezado("Mi cuenta", "Tus datos de acceso y la seguridad de tu cuenta.", "user",
           chips=[("user", user["nombre"]), ("mail", user["email"]), ("shield", ROLES.get(user["rol"], user["rol"]))])

col_propia, col_lado = st.columns([1.2, 1], gap="large")

with col_propia:
    with st.container(border=True):
        titulo("lock", "Cambiar mi contraseña", nivel=4)
        with st.form("form_cambiar_password", clear_on_submit=True, border=False):
            actual = st.text_input("Contraseña actual", type="password")
            nueva = st.text_input("Nueva contraseña", type="password", help=cuenta.REGLA, placeholder="Mínimo 8, con letras y números")
            confirmacion = st.text_input("Confirma la nueva contraseña", type="password")
            if st.form_submit_button("Guardar contraseña", type="primary", icon=":material/save:", width="stretch"):
                ok, mensaje = cuenta.cambiar_password(user["id"], actual, nueva, confirmacion,
                                                      st.session_state.get("_token_sesion"))
                if ok:
                    st.success(mensaje, icon=":material/check_circle:")
                else:
                    st.error(mensaje, icon=":material/error:")

    if user["rol"] == "alumno":  # el tutor habla: voz, velocidad y lectura automática (se guardan en este navegador)
        with st.container(border=True):
            titulo("message", "Voz del tutor", nivel=4)
            st.caption("Bajo cada respuesta del tutor aparece «Escuchar». Aquí eliges cómo suena y si lee solo las "
                       "respuestas nuevas.")
            voz.ajustes()

with col_lado:
    if user["rol"] != "admin":
        titulo("shield", "Consejos de seguridad", nivel=4)
        lista([{"icono": "lock", "titulo": "Usa una contraseña única", "tono": "indigo",
                "texto": f"{cuenta.REGLA} Mejor si además lleva símbolos y no es una palabra común."},
               {"icono": "users", "titulo": "No la compartas", "tono": "violeta",
                "texto": "Nadie necesita conocerla para ayudarte con la app."},
               {"icono": "help", "titulo": "¿La olvidaste?", "tono": "ambar",
                "texto": "Pídele al administrador que la restablezca y cámbiala aquí en cuanto entres."}])
    else:
        with st.container(border=True):
            titulo("key", "Restablecer la contraseña de otro usuario", nivel=4)
            st.caption("Úsalo cuando alguien olvidó su contraseña. Entrégale la nueva por un medio seguro y pídele "
                       "que la cambie al entrar, desde «Mi cuenta».")
            with get_session() as s:
                otros = {u.id: f"{u.nombre} ({u.email}) · {u.rol}"
                         for u in s.scalars(select(Usuario).where(Usuario.id != user["id"]).order_by(Usuario.nombre))}
            if not otros:
                st.info("Todavía no hay otros usuarios.", icon=":material/info:")
            else:
                with st.form("form_restablecer_password", clear_on_submit=True, border=False):
                    destino = st.selectbox("Usuario", list(otros), format_func=otros.get)
                    nueva_r = st.text_input("Nueva contraseña para ese usuario", type="password")
                    confirmacion_r = st.text_input("Confirma la nueva contraseña", type="password", key="confirmar_r")
                    if st.form_submit_button("Restablecer contraseña", icon=":material/lock_reset:", width="stretch"):
                        if nueva_r != confirmacion_r:
                            st.error("La confirmación no coincide con la nueva contraseña.", icon=":material/error:")
                        else:
                            ok, mensaje = cuenta.restablecer_password(user["id"], destino, nueva_r)
                            if ok:
                                st.success(mensaje, icon=":material/check_circle:")
                            else:
                                st.error(mensaje, icon=":material/error:")
