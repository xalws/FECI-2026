import streamlit as st

from core.auth import crear_usuario, login
from core.ui import selector_cascada

st.title("Tutor Universitario")
tab_login, tab_registro = st.tabs(["Iniciar sesión", "Registrarme (alumno)"])

with tab_login:
    with st.form("form_login"):
        email = st.text_input("Correo")
        password = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            u = login(email, password)
            if u:
                st.session_state["user"] = u
                st.rerun()
            else:
                st.error("Correo o contraseña incorrectos.")

with tab_registro:
    nombre = st.text_input("Nombre completo", key="reg_nombre")
    email_r = st.text_input("Correo", key="reg_email")
    pass_r = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="reg_pass")
    st.markdown("**¿Dónde estudias?**")
    sel_reg = selector_cascada(hasta="cuatrimestre", prefix="reg", buscar=False)
    if st.button("Crear cuenta"):
        if sel_reg.get("cuatrimestre") is None:
            st.error("Elige tu universidad, carrera y cuatrimestre/semestre. "
                     "Si no aparecen, pide al administrador que los agregue.")
        else:
            ok, msg = crear_usuario(nombre, email_r, pass_r, "alumno", sel_reg["cuatrimestre"])
            (st.success if ok else st.error)(msg + (" Ya puedes iniciar sesión." if ok else ""))
