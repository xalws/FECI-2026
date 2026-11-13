import streamlit as st

from core import chat, examen, llm, niveles, perfil, progreso, quiz, rag, tutoria
from core.auth import require_login
from core.llm import DIFICULTADES
from core.ui import nombre_tema, selector_cascada

user = require_login(["alumno"])
ss = st.session_state

MODOS = ["💬 Conversación", "✍️ Ejercicio práctico", "📝 Examen"]
LETRAS = "ABCD"


def ocultar_barra_lateral() -> None:
    # Modo concentración: sin menú lateral ni distracciones mientras dura el examen.
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
                "[data-testid='stSidebarCollapseButton'] {display: none !important;}</style>",
                unsafe_allow_html=True)


en_examen = ss.get("examen") is not None
if en_examen:
    ocultar_barra_lateral()
st.title("Examen" if en_examen else "Estudio")

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
    with st.expander("Cambiar mi universidad / carrera / cuatrimestre"):
        sel_nuevo = selector_cascada(hasta="cuatrimestre", prefix="cambiar_perfil", buscar=False)
        if sel_nuevo.get("cuatrimestre") and st.button("Guardar cambio"):
            perfil.asignar_cuatrimestre(user["id"], sel_nuevo["cuatrimestre"])
            st.rerun()
    st.markdown("### Elige tu tema")
    ver = st.radio("Materias a mostrar", ["Mi cuatrimestre", "Todas las materias"], key="ver_materias",
                   help="Con «Todas las materias» puedes estudiar una materia que no sea de tu cuatrimestre.")
    if ver == "Mi cuatrimestre":
        sel = selector_cascada(hasta="tema", prefix="chat", cuatrimestre_id=cuat_id)
    else:
        sel = selector_cascada(hasta="tema", prefix="chat_todas")
tema_id = sel.get("tema")
if tema_id is None:
    st.info("Elige materia, unidad y tema en el menú de la izquierda para empezar.")
    st.stop()
tema_nombre = nombre_tema(tema_id)
prog = progreso.progreso_tema(user["id"], tema_id)
NIVELES = {"apoyo": "refuerzo", "normal": "normal", "avanzado": "avanzado"}
estado = niveles.estado_tema(user["id"], tema_id)
with st.sidebar:
    if prog["total"]:
        st.caption(f"Tu progreso en este tema: {prog['aciertos']}/{prog['total']} aciertos "
                   f"({prog['porcentaje']}%) · modo {NIVELES[prog['nivel']]}")
    else:
        st.caption("Aún no has respondido quizzes de este tema.")
    siguiente = f"{estado['xp_efectivo']}/{estado['siguiente_xp']} XP" if estado["siguiente_xp"] else "nivel máximo"
    st.progress(estado["porcentaje"] / 100,
                text=f"Nivel del tema: {estado['nivel']} · {estado['nombre_nivel']} ({siguiente})")

# Cada vista tiene su propia conversación; si cambia el tema se empieza de cero
for clave in ("conv_id", "conv_ejercicio", "conv_examen", "examen", "examen_resumen", "ejercicio"):
    ss.setdefault(clave, None)
ss.setdefault("intro_hecha", set())  # conversaciones donde el tutor ya saludó o dio la bienvenida de regreso
if ss.get("tema_activo") != tema_id:
    ss.tema_activo = tema_id
    for clave in ("conv_id", "conv_ejercicio", "conv_examen", "examen", "examen_resumen", "ejercicio"):
        ss[clave] = None
    ss.intro_hecha = set()

TIPOS = {"conv_id": "chat", "conv_ejercicio": "ejercicio", "conv_examen": "examen"}


def nueva_conversacion(clave: str, titulo: str) -> int:
    ss[clave] = chat.crear_conversacion(user["id"], tema_id, titulo, TIPOS[clave])
    return ss[clave]


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


# ----------------------------------------------------------------------------------------------------------
# Vista 1: conversación
# ----------------------------------------------------------------------------------------------------------
def _clave_intro(conv_id: int | None) -> str:
    return "nueva" if conv_id is None else f"conv{conv_id}"


def cambiar_conversacion() -> None:
    # Al elegir otra conversación, el tutor vuelve a dar la bienvenida (de regreso o de chat nuevo).
    ss.conv_id = ss["conv_picker"] or None  # 0 = «Nueva conversación»
    ss.intro_hecha.discard(_clave_intro(ss.conv_id))


def fragmentos_para(historial: list[dict]) -> list[dict]:
    # Material relacionado con lo último que preguntó el alumno; si no hay nada, fragmentos al azar del tema.
    preguntas = [m["contenido"] for m in historial if m["rol"] == "user"]
    encontrados = rag.buscar(tema_id, preguntas[-1]) if preguntas else []
    return encontrados or rag.chunks_aleatorios(tema_id, 3)


def accion_tutor(intencion: str, texto_alumno: str | None = None) -> None:
    # El tutor guía la conversación: inicia la lección, la retoma, da retroalimentación o saluda.
    try:
        with st.spinner("Pensando…"):
            conv = ss.conv_id or nueva_conversacion(
                "conv_id", f"Lección: {tema_nombre}" if intencion == "iniciar" else (texto_alumno or "Conversación"))
            historial = chat.listar_mensajes(conv)
            if texto_alumno:
                chat.guardar_mensaje(conv, "user", texto_alumno)
            if intencion == "saludo":
                respuesta = tutoria.SALUDO.format(tema=tema_nombre)
            elif intencion == "retro":
                respuesta = tutoria.retroalimentar(tema_nombre, historial, fragmentos_para(historial))
            elif intencion == "continuar" and historial:
                respuesta = tutoria.continuar_leccion(tema_nombre, historial, fragmentos_para(historial), prog["nivel"])
            else:  # iniciar (o continuar sin nada previo)
                respuesta = tutoria.iniciar_leccion(tema_nombre, tutoria.objetivos_del_tema(tema_id),
                                                    rag.chunks_aleatorios(tema_id, 3), prog["nivel"])
            chat.guardar_mensaje(conv, "assistant", respuesta)
        ss.intro_hecha.update({"nueva", _clave_intro(conv)})
        st.rerun()
    except Exception as e:
        st.error(str(e))


def vista_conversacion() -> None:
    previas = chat.conversaciones_del_tema(user["id"], tema_id)
    # Se usa 0 y no None para «Nueva conversación»: con None Streamlit mostraría «Choose an option»
    etiquetas = {0: "➕ Nueva conversación",
                 **{c["id"]: f"{c['fecha']:%d/%m %H:%M} · {c['titulo'][:38]}" for c in previas}}
    if ss.conv_id and ss.conv_id not in etiquetas:
        etiquetas[ss.conv_id] = "Conversación actual"
    ss["conv_picker"] = ss.conv_id or 0  # sincroniza el selector antes de crearlo
    st.selectbox("Conversación", list(etiquetas), format_func=etiquetas.get, key="conv_picker",
                 on_change=cambiar_conversacion, label_visibility="collapsed")

    mensajes = chat.listar_mensajes(ss.conv_id) if ss.conv_id else []
    for m in mensajes:
        with st.chat_message(m["rol"]):
            st.markdown(m["contenido"])

    if _clave_intro(ss.conv_id) not in ss.intro_hecha:
        with st.chat_message("assistant"):
            if not mensajes:
                st.markdown(f"¡Hola! Soy tu tutor de **{tema_nombre}**. ¿Iniciamos la lección o tienes una pregunta?")
                b1, b2 = st.columns(2)
                if b1.button("▶️ Iniciar la lección", type="primary", key="btn_iniciar"):
                    accion_tutor("iniciar")
                if b2.button("❓ Tengo una pregunta", key="btn_pregunta"):
                    ss.intro_hecha.add("nueva")
                    st.rerun()
            else:
                st.markdown("¡Qué bueno verte de nuevo! Retomamos esta conversación. ¿Qué prefieres?")
                b1, b2, b3 = st.columns(3)
                if b1.button("📝 Retroalimentación", key="btn_retro"):
                    accion_tutor("retro")
                if b2.button("▶️ Continuar donde lo dejamos", type="primary", key="btn_continuar"):
                    accion_tutor("continuar")
                if b3.button("❓ Otra pregunta", key="btn_otra"):
                    ss.intro_hecha.add(_clave_intro(ss.conv_id))
                    st.rerun()
    elif not mensajes:
        st.caption(f"Pregúntame lo que quieras sobre **{tema_nombre}**. También puedes escribir «comencemos».")

    pregunta = st.chat_input("Escribe tu pregunta o «comencemos»…")
    if not pregunta:
        return
    intencion = tutoria.detectar_intencion(pregunta)
    if intencion:  # «comencemos», «continuemos», «hola»…: no son preguntas sobre el contenido
        accion_tutor(intencion, pregunta)
        return
    conv = ss.conv_id or nueva_conversacion("conv_id", pregunta)
    ss.intro_hecha.update({"nueva", _clave_intro(conv)})
    historial = chat.listar_mensajes(conv)
    fragmentos = rag.buscar(tema_id, construir_consulta(historial, pregunta))
    chat.guardar_mensaje(conv, "user", pregunta)
    with st.chat_message("user"):
        st.markdown(pregunta)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Pensando…"):
                respuesta = llm.responder(tema_nombre, pregunta, fragmentos, historial, prog["nivel"])
            if respuesta != llm.SIN_INFO:
                respuesta += texto_fuentes(fragmentos)
            else:
                chat.registrar_sin_respuesta(user["id"], tema_id, pregunta)
            st.markdown(respuesta)
            chat.guardar_mensaje(conv, "assistant", respuesta)
        except Exception as e:
            st.error(str(e))


# ----------------------------------------------------------------------------------------------------------
# Vista 2: ejercicio práctico (el ejercicio, tu respuesta y la calificación, todo en una pantalla)
# ----------------------------------------------------------------------------------------------------------
def vista_ejercicio() -> None:
    ej = ss.ejercicio
    if ej is None:
        st.write(f"Un ejercicio práctico sobre **{tema_nombre}**. Lo resuelves a tu ritmo y la IA lo califica de 0 a 10.")
        if st.button("Plantéame un ejercicio", type="primary"):
            try:
                with st.spinner("Preparando el ejercicio…"):
                    fragmentos = rag.chunks_aleatorios(tema_id, 3)
                    enunciado = llm.responder(tema_nombre, "Plantéame un ejercicio práctico sobre este tema.",
                                              fragmentos, [], prog["nivel"])
                if not fragmentos or enunciado == llm.SIN_INFO:
                    st.warning("El maestro todavía no ha subido material para este tema.")
                    return
                conv = nueva_conversacion("conv_ejercicio", "Ejercicio práctico")
                chat.guardar_mensaje(conv, "assistant", enunciado)
                ss.ejercicio = {"enunciado": enunciado, "fragmentos": fragmentos, "resultado": None}
                st.rerun()
            except Exception as e:
                st.error(str(e))
        return

    st.markdown(ej["enunciado"])
    st.divider()
    if ej["resultado"]:
        r = ej["resultado"]
        (st.success if r["puntaje"] >= 6 else st.warning)(f"**Calificación: {r['puntaje']}/10**")
        st.markdown(r["retroalimentacion"])
        if st.button("Otro ejercicio", type="primary"):
            ss.ejercicio = None
            st.rerun()
        return

    resp_ej = st.text_area("Tu respuesta", key="resp_ejercicio", height=180)
    b1, b2 = st.columns([1, 3])
    if b2.button("Descartar ejercicio"):
        ss.ejercicio = None
        st.rerun()
    if b1.button("Calificar", type="primary"):
        if not resp_ej.strip():
            st.warning("Escribe tu respuesta primero.")
            return
        try:
            with st.spinner("Calificando…"):
                r = llm.calificar_ejercicio(ej["enunciado"], resp_ej, ej["fragmentos"])
            progreso.guardar_intento(user["id"], tema_id, ej["enunciado"], resp_ej, r["puntaje"], r["retroalimentacion"])
            chat.guardar_mensaje(ss.conv_ejercicio, "user", f"**Mi respuesta al ejercicio:**\n\n{resp_ej}")
            chat.guardar_mensaje(ss.conv_ejercicio, "assistant",
                                 f"**Calificación: {r['puntaje']}/10**\n\n{r['retroalimentacion']}")
            ej["resultado"] = r
            st.rerun()
        except Exception as e:
            st.error(str(e))


# ----------------------------------------------------------------------------------------------------------
# Vista 3: examen (pantalla aislada: solo la pregunta, sin menú ni conversación)
# ----------------------------------------------------------------------------------------------------------
def vista_examen_inicio() -> None:
    if ss.examen_resumen:
        st.success("Resultado de tu último examen")
        st.markdown(ss.examen_resumen)
        st.divider()
    inicial = examen.dificultad_inicial(prog["nivel"])
    st.write(f"Examen de varias preguntas sobre **{tema_nombre}**. Empiezas en dificultad "
             f"**{DIFICULTADES[inicial]}** según tu nivel en el tema; mientras aciertes, las preguntas serán más "
             "difíciles, y si fallas bajan un poco.")
    st.info("Durante el examen se oculta todo lo demás (menú y conversación) para que puedas concentrarte. "
            "Después de cada pregunta verás la respuesta correcta y su explicación.")
    total = st.number_input("Número de preguntas", min_value=3, max_value=10, value=examen.PREGUNTAS_POR_DEFECTO, step=1)
    if st.button("Comenzar examen", type="primary"):
        nueva_conversacion("conv_examen", "Examen")
        ss.examen = examen.nuevo_examen(int(total), prog["nivel"])
        ss.examen["xp_inicial"], ss.examen["nivel_inicial"] = estado["xp_efectivo"], estado["nivel"]
        ss.examen["fase"] = "pregunta"
        ss.examen_resumen = None
        st.rerun()


def responder_examen(q: dict, eleccion: int) -> None:
    ex = ss.examen
    r = quiz.evaluar(q["id"], user["id"], eleccion)
    veredicto = "✅ ¡Correcto!" if r["es_correcta"] else "❌ Incorrecto"
    opciones_txt = "\n".join(f"- {LETRAS[i]}) {o}" for i, o in enumerate(q["opciones"]))
    chat.guardar_mensaje(
        ss.conv_examen, "assistant",
        f"**Quiz {ex['numero']}/{ex['total']} (dificultad {DIFICULTADES[q['dificultad']]}):** {q['pregunta']}\n\n"
        f"{opciones_txt}\n\n**Tu respuesta:** {LETRAS[eleccion]} — {veredicto}\n\n"
        f"**Respuesta correcta:** {LETRAS[r['indice_correcto']]}\n\n{r['explicacion']}")
    ex["revision"] = {"numero": ex["numero"], "pregunta": q["pregunta"], "opciones": q["opciones"],
                      "dificultad": q["dificultad"], "elegida": eleccion, "correcta": r["indice_correcto"],
                      "acerto": r["es_correcta"], "explicacion": r["explicacion"]}
    examen.registrar_resultado(ex, r["es_correcta"])
    if examen.terminado(ex):
        despues = niveles.estado_tema(user["id"], tema_id)
        resumen = examen.resumen_texto(ex) + "\n\n" + examen.progreso_texto(ex["nivel_inicial"], ex["xp_inicial"], despues)
        chat.guardar_mensaje(ss.conv_examen, "assistant", resumen)
        ss.examen_resumen = resumen
        ex["fase"] = "final"
    st.rerun()


def vista_examen_en_curso() -> None:
    ex = ss.examen
    contestadas = len(ex["resultados"])
    st.progress(contestadas / ex["total"], text=f"{contestadas} de {ex['total']} respondidas · {tema_nombre}")

    rev = ex.get("revision")
    if rev:  # retroalimentación de la pregunta que acabas de contestar
        st.caption(f"Pregunta {rev['numero']} · dificultad {DIFICULTADES[rev['dificultad']]}")
        st.markdown(f"**{rev['pregunta']}**")
        for i, o in enumerate(rev["opciones"]):
            marca = "✅" if i == rev["correcta"] else ("❌" if i == rev["elegida"] else "▫️")
            st.markdown(f"{marca} **{LETRAS[i]})** {o}")
        if rev["acerto"]:
            st.success("¡Correcto!")
        else:
            st.error(f"Incorrecto. Elegiste {LETRAS[rev['elegida']]}; la correcta era {LETRAS[rev['correcta']]}.")
        st.markdown(rev["explicacion"])
        ultimo = examen.terminado(ex)
        if st.button("Ver resultados" if ultimo else "Siguiente pregunta", type="primary"):
            if ultimo:
                ss.examen = None
            else:
                ex["revision"] = None
            st.rerun()
        return

    if ex["quiz"] is None:
        error = ""
        try:
            with st.spinner("Preparando la pregunta…"):
                ex["quiz"] = quiz.crear_quiz(tema_id, ss.conv_examen, ex["dificultad"], user["id"])
        except Exception as e:
            error = str(e)
        if ex["quiz"] is None:
            if error:
                st.error(error)
                st.button("Reintentar")  # al pulsarlo la página se ejecuta de nuevo y vuelve a intentar
            else:
                st.warning("El maestro todavía no ha subido material para este tema.")
            if st.button("Salir del examen"):
                ss.examen = None
                st.rerun()
            return
    q = ex["quiz"]
    st.caption(f"Pregunta {ex['numero']} de {ex['total']} · dificultad {DIFICULTADES[q['dificultad']]}")
    st.markdown(f"### {q['pregunta']}")
    eleccion = st.radio("Elige una opción", range(4), index=None, key=f"quiz_{q['id']}",
                        format_func=lambda i: f"{LETRAS[i]}) {q['opciones'][i]}", label_visibility="collapsed")
    b1, b2 = st.columns([1, 3])
    if b2.button("Abandonar examen", key=f"abandonar_{q['id']}"):
        ss.examen = None
        st.rerun()
    if b1.button("Responder", type="primary", key=f"resp_{q['id']}"):
        if eleccion is None:
            st.warning("Elige una opción primero.")
        else:
            responder_examen(q, eleccion)


def vista_examen() -> None:
    if ss.examen is None:
        vista_examen_inicio()
    else:
        vista_examen_en_curso()


# ----------------------------------------------------------------------------------------------------------
# Selector de vista (durante un examen se bloquea para no distraerse)
# ----------------------------------------------------------------------------------------------------------
if ss.examen is not None:
    ss["modo_chat"] = MODOS[2]
    vista_examen_en_curso()
else:
    modo = st.radio("Modo", MODOS, horizontal=True, key="modo_chat", label_visibility="collapsed")
    st.divider()
    if modo == MODOS[0]:
        vista_conversacion()
    elif modo == MODOS[1]:
        vista_ejercicio()
    else:
        vista_examen()
