import streamlit as st

from core import chat
from core.auth import require_login

user = require_login(["alumno"])

st.title("Mi historial")

texto = st.text_input("Buscar en mis conversaciones",
                      placeholder="")
convs = chat.listar_conversaciones(user["id"], texto)
if not convs:
    st.info("No se encontraron conversaciones con ese texto." if texto.strip()
            else "Todavía no tienes conversaciones.")
    st.stop()

etiquetas = {c["id"]: f"{c['fecha']:%d/%m/%Y %H:%M} · {c['materia']} › {c['tema']} · {c['titulo'][:40]}"
             for c in convs}
elegida = st.selectbox("Conversación", list(etiquetas), format_func=etiquetas.get)

st.divider()
for m in chat.listar_mensajes(elegida):
    with st.chat_message(m["rol"]):
        st.markdown(m["contenido"])
