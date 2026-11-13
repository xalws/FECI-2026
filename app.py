# Router principal
import streamlit as st

from core.auth import iniciar_db

st.set_page_config(page_title="Tutor Universitario", page_icon="🎓", layout="wide")
iniciar_db()

# rol
PAGINAS_POR_ROL = {
    "alumno": [
        ("vistas/chat_alumno.py", "Chat de estudio", "", "chat"),
        ("vistas/mi_progreso.py", "Mi progreso", "", "progreso"),
        ("vistas/historial.py", "Mi historial", "", "historial"),
    ],
    "maestro": [
        ("vistas/panel_maestro.py", "Material de la IA", "", "material"),
        ("vistas/estadisticas.py", "Estadísticas", "", "estadisticas"),
    ],
    "admin": [
        ("vistas/admin.py", "Administración", "", "admin"),
        ("vistas/panel_maestro.py", "Material de la IA", "", "material"),
        ("vistas/estadisticas.py", "Estadísticas", "", "estadisticas"),
    ],
}

user = st.session_state.get("user")
paginas = PAGINAS_POR_ROL.get(user["rol"]) if user else None

if paginas:
    nav = st.navigation([st.Page(ruta, title=titulo, icon=icono, url_path=url)
                         for ruta, titulo, icono, url in paginas])
else:
    # sesión inválida o rol desconocido
    st.session_state.pop("user", None)  
    nav = st.navigation([st.Page("vistas/login.py", title="Iniciar sesión", icon="", url_path="login")],
                        position="hidden")
nav.run()
