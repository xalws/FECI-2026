"""Mi perfil: lo que ven mis compañeros de clase, la vitrina de logros que elijo mostrar y el catálogo completo."""
import streamlit as st

from core import competencia, logros
from core.auth import require_login
from core.estilo import encabezado, logros_grid, titulo, vitrina, zona_horaria
from core.perfil_ui import mostrar_perfil

user = require_login(["alumno"])
ss = st.session_state
zona = zona_horaria()

datos = logros.datos_alumno(user["id"], zona)
p = competencia.perfil_publico(user["id"], user["id"], zona, datos)
evaluados = p["logros"]
logros.revisar_nuevos(user["id"], zona, datos)

aviso = ss.pop("aviso_vitrina", None)
if aviso:
    st.toast(aviso[0], icon=":material/check_circle:" if aviso[1] else ":material/error:")

mostrar_perfil(p, propio=True)

# ---------------------------------------------------------------------------------------------------------------
# Vitrina: qué logros se ven en mi perfil
# ---------------------------------------------------------------------------------------------------------------
titulo("star", "Elige qué logros mostrar")
st.caption(f"Tus compañeros de clase ven estos logros en tu perfil (hasta {logros.MAX_VITRINA}). Si no eliges ninguno, "
           "se muestran tus mejores.")
conseguidos = {l["id"]: l for l in evaluados if l["nivel"]}
if not conseguidos:
    st.info("Cuando consigas tu primer logro podrás elegirlo aquí.", icon=":material/emoji_events:")
else:
    actuales = [i for i in logros.vitrina_de(user["id"]) if i in conseguidos]
    with st.form("form_vitrina", border=False):
        elegidos = st.multiselect(
            "Logros en mi vitrina", list(conseguidos), default=actuales, max_selections=logros.MAX_VITRINA,
            placeholder="Elige los logros que quieres mostrar",
            format_func=lambda i: f"{conseguidos[i]['titulo']} · {conseguidos[i]['nombre_nivel']}")
        if st.form_submit_button("Guardar vitrina", type="primary", icon=":material/save:"):
            ok, msg = logros.guardar_vitrina(user["id"], elegidos)
            ss["aviso_vitrina"] = (msg, ok)
            st.rerun()

# ---------------------------------------------------------------------------------------------------------------
# Catálogo completo por categorías
# ---------------------------------------------------------------------------------------------------------------
resumen = p["resumen"]
titulo("award", f"Todos los logros · {resumen['medallas']} de {resumen['maximas']} medallas")
st.caption("Cada logro tiene 4 niveles: Bronce, Plata, Élite y Oro. El oro es el más difícil de conseguir.")
categorias = list(logros.CATEGORIAS)
pestañas = st.tabs([f"{logros.CATEGORIAS[c][0]} ({sum(1 for l in evaluados if l['categoria'] == c and l['nivel'])}"
                    f"/{sum(1 for l in evaluados if l['categoria'] == c)})" for c in categorias])
for pestaña, categoria in zip(pestañas, categorias):
    with pestaña:
        logros_grid([l for l in evaluados if l["categoria"] == categoria])
