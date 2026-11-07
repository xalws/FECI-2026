import streamlit as st

from core.auth import crear_usuario, login

st.title("🎓 Tutor IA Universitario")
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
    with st.form("form_registro"):
        nombre = st.text_input("Nombre completo")
        email_r = st.text_input("Correo", key="email_r")
        pass_r = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="pass_r")
        if st.form_submit_button("Crear cuenta"):
            ok, msg = crear_usuario(nombre, email_r, pass_r, "alumno")
            (st.success if ok else st.error)(msg + (" Ya puedes iniciar sesión." if ok else ""))
