import streamlit as st

from core import llm, chat
from core.auth import require_login
from core.estilo import encabezado, fecha_local, insignias

user = require_login(["alumno"])

# tipo de conversación -> (nombre, tono, ícono)
TIPOS = {"chat": ("Conversación", "indigo", "message"), "ejercicio": ("Ejercicio práctico", "cielo", "bulb"),
         "examen": ("Examen", "violeta", "clipboard")}

encabezado("Mi historial", "Vuelve a leer tus conversaciones con el tutor, tus ejercicios y tus exámenes.", "history")

texto = st.text_input("Buscar en mis conversaciones", placeholder="Busca por materia, tema o una palabra del chat",
                      icon=":material/search:")
convs = chat.listar_conversaciones(user["id"], texto)
if not convs:
    st.info("No se encontraron conversaciones con ese texto." if texto.strip()
            else "Todavía no tienes conversaciones. Empieza una en «Estudio».", icon=":material/forum:")
    st.stop()

etiquetas = {c["id"]: f"{fecha_local(c['fecha']):%d/%m/%Y %H:%M} · {c['materia']} › {c['tema']} · {c['titulo'][:40]}"
             for c in convs}
elegida = st.selectbox(f"Conversación ({len(convs)} en total)", list(etiquetas), format_func=etiquetas.get)
conv = next(c for c in convs if c["id"] == elegida)
nombre_tipo, tono, icono = TIPOS.get(conv["tipo"], TIPOS["chat"])
if conv["titulo"] == "Repaso de errores":
    nombre_tipo, tono, icono = "Repaso de errores", "ambar", "refresh"

with st.container(border=True):
    insignias((nombre_tipo, tono, icono), (conv["materia"], "indigo", "book"), (conv["tema"], "verde", "layers"),
              (f"{fecha_local(conv['fecha']):%d/%m/%Y · %H:%M}", "rosa", "calendar"))
    mensajes = chat.listar_mensajes(elegida)
    if not mensajes:
        st.caption("Esta conversación no tiene mensajes.")
    for m in mensajes:
        with st.chat_message(m["rol"]):
            st.markdown(llm.para_mostrar(m["contenido"]))
