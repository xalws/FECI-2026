import streamlit as st

from core import chat, llm, perfil, progreso, quiz, rag
from core.auth import require_login
from core.ui import nombre_tema, selector_cascada

user = require_login(["alumno"])
ss = st.session_state

st.title("Chat de estudio")

cuat_id = perfil.cuatrimestre_de(user["id"])
if cuat_id is None:
    st.subheader("Completa tu perfil")
    st.write("Elige tu universidad, carrera y cuatrimestre/semestre.")
    sel_perfil = selector_cascada(hasta="cuatrimestre", prefix="perfil", buscar=False)
    if sel_perfil.get("cuatrimestre") and st.button("Guardar perfil", type="primary"):
        perfil.asignar_cuatrimestre(user["id"], sel_perfil["cuatrimestre"])
        st.rerun()
    st.stop()

with st.sidebar:
    st.divider()
    datos = perfil.datos_academicos(cuat_id)
    if datos:
        st.caption(" · ".join(datos))
    st.markdown("### Elige tu tema")
    sel = selector_cascada(hasta="tema", prefix="chat", cuatrimestre_id=cuat_id)
tema_id = sel.get("tema")
if tema_id is None:
    st.info("Elige materia, unidad y tema en el menú de la izquierda para empezar.")
    st.stop()
tema_nombre = nombre_tema(tema_id)
prog = progreso.progreso_tema(user["id"], tema_id)
NIVELES = {"apoyo": "refuerzo", "normal": "normal", "avanzado": "avanzado"}
with st.sidebar:
    if prog["total"]:
        st.caption(f"Tu progreso en este tema: {prog['aciertos']}/{prog['total']} aciertos "
                   f"({prog['porcentaje']}%) · modo {NIVELES[prog['nivel']]}")
    else:
        st.caption("Aún no has respondido quizzes de este tema.")

# Si cambia el tema, se empieza una conversación nueva
ss.setdefault("conv_id", None)
ss.setdefault("quiz_activo", None)
if ss.get("tema_activo") != tema_id:
    ss.tema_activo, ss.conv_id, ss.quiz_activo = tema_id, None, None

st.divider()
c1, c2, c3 = st.columns(3)
accion = None
if c1.button("Ponme un quiz"):
    accion = "quiz"
if c2.button("Ejercicio práctico"):
    accion = "ejercicio"
if c3.button("Nueva conversación"):
    ss.conv_id, ss.quiz_activo = None, None
    st.rerun()

# Historial de la conversación actual
if ss.conv_id:
    for m in chat.listar_mensajes(ss.conv_id):
        with st.chat_message(m["rol"]):
            st.markdown(m["contenido"])
else:
    st.caption(f"Pregúntame lo que quieras sobre **{tema_nombre}**.")


def asegurar_conversacion(titulo: str) -> int:
    if not ss.conv_id:
        ss.conv_id = chat.crear_conversacion(user["id"], tema_id, titulo)
    return ss.conv_id


def construir_consulta(historial: list[dict], pregunta: str) -> str:
    if len(pregunta.split()) < 6:
        previas = [m["contenido"] for m in historial if m["rol"] == "user"]
        if previas:
            return previas[-1] + " " + pregunta
    return pregunta


def texto_fuentes(fragmentos: list[dict]) -> str:
    # Lista única de "archivo, pág. N" de los 3 fragmentos más parecidos a la pregunta.
    vistas = []
    for f in sorted(fragmentos, key=lambda f: f.get("score", 0), reverse=True)[:3]:
        if f.get("archivo"):
            fuente = f"{f['archivo']}, pág. {f['pagina']}" if f.get("pagina") else f["archivo"]
            if fuente not in vistas:
                vistas.append(fuente)
    return f"\n\n*Fuentes: {'; '.join(vistas)}*" if vistas else ""


# Mensaje nuevo o ejercicio
pregunta = st.chat_input("Escribe tu pregunta sobre este tema…")
if pregunta or accion == "ejercicio":
    conv = asegurar_conversacion(pregunta or "Ejercicio práctico")
    historial = chat.listar_mensajes(conv)
    if accion == "ejercicio" and not pregunta:
        texto = "Plantéame un ejercicio práctico sobre este tema."
        fragmentos = rag.chunks_aleatorios(tema_id, 3)
    else:
        texto = pregunta
        fragmentos = rag.buscar(tema_id, construir_consulta(historial, pregunta))

    chat.guardar_mensaje(conv, "user", texto)
    with st.chat_message("user"):
        st.markdown(texto)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Pensando…"):
                respuesta = llm.responder(tema_nombre, texto, fragmentos, historial, prog["nivel"])
            if respuesta != llm.SIN_INFO:
                respuesta += texto_fuentes(fragmentos)
            elif pregunta:
                chat.registrar_sin_respuesta(user["id"], tema_id, pregunta)
            st.markdown(respuesta)
            chat.guardar_mensaje(conv, "assistant", respuesta)
        except Exception as e:
            st.error(str(e))

# Quiz
if accion == "quiz":
    conv = asegurar_conversacion("Quiz")
    try:
        with st.spinner("Generando quiz…"):
            ss.quiz_activo = quiz.crear_quiz(tema_id, conv, prog["nivel"])
        if ss.quiz_activo is None:
            st.warning("El maestro todavía no ha subido material para este tema.")
    except Exception as e:
        st.error(str(e))

q = ss.quiz_activo
if q:
    letras = "ABCD"
    with st.chat_message("assistant"):
        st.markdown(f"**Quiz:** {q['pregunta']}")
        eleccion = st.radio("Elige una opción", range(4), index=None, key=f"quiz_{q['id']}",
                            format_func=lambda i: f"{letras[i]}) {q['opciones'][i]}")
        if st.button("Responder", key=f"resp_{q['id']}"):
            if eleccion is None:
                st.warning("Elige una opción primero.")
            else:
                r = quiz.evaluar(q["id"], user["id"], eleccion)
                veredicto = "✅ ¡Correcto!" if r["es_correcta"] else "❌ Incorrecto"
                opciones_txt = "\n".join(f"- {letras[i]}) {o}" for i, o in enumerate(q["opciones"]))
                chat.guardar_mensaje(
                    ss.conv_id, "assistant",
                    f"**Quiz:** {q['pregunta']}\n\n{opciones_txt}\n\n"
                    f"**Tu respuesta:** {letras[eleccion]} — {veredicto}\n\n"
                    f"**Respuesta correcta:** {letras[r['indice_correcto']]}\n\n{r['explicacion']}")
                ss.quiz_activo = None
                st.rerun()
