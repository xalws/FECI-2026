import streamlit as st

from core import estilo, sesion, tema
from core.auth import crear_usuario, login
from core.ui import selector_cascada

col_marca, col_acceso = st.columns([1.15, 1], gap="large", vertical_alignment="center")

with col_marca:
    estilo.marca_acceso()

with col_acceso:
    with st.container(border=True, key="tarjeta_acceso"):
        st.markdown('<div class="tu-acceso-bienvenida">Te damos la bienvenida</div>'
                    '<div class="tu-acceso-ayuda">Entra con tu cuenta o regístrate como alumno.</div>',
                    unsafe_allow_html=True)
        tab_login, tab_registro = st.tabs([":material/login: Iniciar sesión", ":material/person_add: Registrarme (alumno)"])
        carga = st.empty()  # aquí se dibuja la pantalla de carga al pulsar «Entrar»

        with tab_login:
            with st.form("form_login", border=False):
                email = st.text_input("Correo", placeholder="tu.correo@ejemplo.com")
                password = st.text_input("Contraseña", type="password", placeholder="Tu contraseña")
                recordar = st.checkbox("Mantener mi sesión iniciada", value=True,
                                       help="Así no tienes que escribir tu contraseña si recargas la página. "
                                            "Dura 14 días; desmárcala en computadoras compartidas.")
                if st.form_submit_button("Entrar", type="primary", icon=":material/arrow_forward:", width="stretch"):
                    estilo.mostrar_carga(carga)  # de inmediato: comprobar la contraseña y abrir la sesión puede tardar
                    u = login(email, password)
                    if u:
                        st.session_state["user"] = u
                        st.session_state.pop("_sesion_cerrada", None)
                        st.session_state["_cargando"] = True  # app.py la mantiene hasta que cargue la primera pantalla
                        if recordar:
                            sesion.recordar(u["id"])
                        st.rerun()
                    else:
                        carga.empty()
                        st.error("Correo o contraseña incorrectos.", icon=":material/error:")
            st.caption(":material/help: ¿Olvidaste tu contraseña? Pídele al administrador que la restablezca; "
                       "después puedes cambiarla en «Mi cuenta».")

        with tab_registro:
            nombre = st.text_input("Nombre completo", key="reg_nombre", placeholder="Como aparecerá en la app")
            email_r = st.text_input("Correo", key="reg_email", placeholder="tu.correo@ejemplo.com")
            pass_r = st.text_input("Contraseña (mínimo 6 caracteres)", type="password", key="reg_pass")
            st.markdown("**¿Dónde estudias?**")
            sel_reg = selector_cascada(hasta="cuatrimestre", prefix="reg", buscar=False)
            if st.button("Crear cuenta", type="primary", icon=":material/person_add:", width="stretch"):
                if sel_reg.get("cuatrimestre") is None:
                    st.error("Elige tu universidad, carrera y cuatrimestre/semestre. "
                             "Si no aparecen, pide al administrador que los agregue.")
                else:
                    ok, msg = crear_usuario(nombre, email_r, pass_r, "alumno", sel_reg["cuatrimestre"])
                    (st.success if ok else st.error)(msg + (" Ya puedes iniciar sesión." if ok else ""))
    tema.boton(en_barra_lateral=False)
