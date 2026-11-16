# Router principal
from pathlib import Path

import streamlit as st

from core import sesion, tema
from core.auth import iniciar_db
from core.estilo import aplicar_estilo, transicion

st.set_page_config(page_title="Tutor Universitario", page_icon="🎓", layout="wide")
iniciar_db()
tema.restaurar_sesion()  # tras cambiar de modo claro/oscuro la página se recarga: vuelve a su sesión
sesion.restaurar()       # «Recordarme»: si el navegador trae un código vigente, se recupera la sesión
sesion.aplicar_cookie_pendiente()  # escribe o borra la cookie si el inicio o el cierre de sesión lo dejó pendiente
aplicar_estilo()

ASSETS = Path(__file__).parent / "assets"

# (ruta, título, ícono, url)
CHAT = ("vistas/chat_alumno.py", "Estudio", ":material/school:", "chat")
PROGRESO = ("vistas/mi_progreso.py", "Mi progreso", ":material/insights:", "progreso")
HISTORIAL = ("vistas/historial.py", "Mi historial", ":material/history:", "historial")
CUENTA = ("vistas/cuenta.py", "Mi cuenta", ":material/manage_accounts:", "cuenta")
RETICULA = ("vistas/reticula.py", "Retícula", ":material/account_tree:", "reticula")
MATERIAL = ("vistas/panel_maestro.py", "Material de la IA", ":material/upload_file:", "material")
ESTADISTICAS = ("vistas/estadisticas.py", "Estadísticas", ":material/monitoring:", "estadisticas")
ADMIN = ("vistas/admin.py", "Administración", ":material/admin_panel_settings:", "admin")

# rol -> secciones del menú
PAGINAS_POR_ROL = {
    "alumno": {"Aprender": [CHAT, PROGRESO, HISTORIAL], "Cuenta": [CUENTA]},
    "maestro": {"Docencia": [RETICULA, MATERIAL, ESTADISTICAS], "Cuenta": [CUENTA]},
    "admin": {"Administración": [ADMIN], "Docencia": [RETICULA, MATERIAL, ESTADISTICAS], "Cuenta": [CUENTA]},
}

user = st.session_state.get("user")
secciones = PAGINAS_POR_ROL.get(user["rol"]) if user else None

if secciones:
    st.logo(str(ASSETS / "logo.svg"), icon_image=str(ASSETS / "icono.svg"), size="large")
    nav = st.navigation({seccion: [st.Page(ruta, title=titulo, icon=icono, url_path=url)
                                   for ruta, titulo, icono, url in paginas]
                         for seccion, paginas in secciones.items()})
else:
    # sesión inválida o rol desconocido
    st.session_state.pop("user", None)
    nav = st.navigation([st.Page("vistas/login.py", title="Iniciar sesión", icon=":material/login:", url_path="login")],
                        position="hidden")
transicion(nav.url_path or nav.title)  # al cambiar de pantalla, el contenido vuelve a entrar animado
nav.run()
