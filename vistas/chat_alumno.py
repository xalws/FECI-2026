import streamlit as st

from core import chat, examen, llm, material, niveles, perfil, progreso, quiz, rag, tutoria
from core.auth import require_login
from core.llm import DIFICULTADES
from core.ui import nombre_tema, selector_cascada

user = require_login(["alumno"])
ss = st.session_state

# Los modos usan iconos Material dentro de la etiqueta (el resto del código los usa por índice)
MODOS = [":material/chat: Conversación", ":material/edit_note: Ejercicio práctico",
         ":material/assignment: Examen", ":material/replay: Repasar errores"]
LETRAS = "ABCD"

# Iconos SVG
SVG = {
    "book": '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/>',
    "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "layers": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "x": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "circle": '<circle cx="12" cy="12" r="10"/>',
}
COLOR_OK, COLOR_MAL, COLOR_NEUTRO = "#568C5E", "#B5533C", "#89A685"


def titulo(icono: str, texto: str, nivel: int = 3):
    """Encabezado con icono SVG en línea."""
    size = 30 if nivel == 1 else 22
    st.markdown(
        f'<div class="tit"><svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{SVG[icono]}</svg><h{nivel}>{texto}</h{nivel}></div>',
        unsafe_allow_html=True,
    )


def opcion_md(i: int, texto: str, estado: str) -> None:
    """Opción de quiz con icono SVG: estado = 'ok' | 'mal' | 'neutro'."""
    color = {"ok": COLOR_OK, "mal": COLOR_MAL}.get(estado, COLOR_NEUTRO)
    icono = {"ok": "check", "mal": "x"}.get(estado, "circle")
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" '
           f'style="vertical-align:-3px;margin-right:6px">{SVG[icono]}</svg>')
    st.markdown(f"{svg}**{LETRAS[i]})** {texto}", unsafe_allow_html=True)


# Estilo
st.markdown(
    """
    <style>
    /* Encabezados con icono SVG */
    .tit { display: flex; align-items: center; gap: .6rem; margin: .6rem 0 .4rem; }
    .tit h1, .tit h2, .tit h3 { margin: 0; padding: 0; }
    .tit svg { flex-shrink: 0; }
    /* Burbujas de chat redondeadas */
    div[data-testid="stChatMessage"] { border-radius: 14px; padding: 12px 16px; }
    /* Botones redondeados */
    .stButton > button { border-radius: 10px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


def nombre_dificultad(d) -> str:
    return DIFICULTADES.get(d, "")  # las preguntas antiguas no guardaron su dificultad


def ocultar_barra_lateral() -> None:
    # Modo concentración
    st.markdown("<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'], "
                "[data-testid='stSidebarCollapseButton'] {display: none !important;}</style>",
                unsafe_allow_html=True)


en_examen = ss.get("examen") is not None
if en_examen:
    ocultar_barra_lateral()
    if ss.examen.get("tipo") == "repaso":
        titulo("refresh", "Repaso de errores", nivel=1)
    else:
        titulo("clipboard", "Examen", nivel=1)
else:
    titulo("book", "Estudio", nivel=1)

cuat_id = perfil.cuatrimestre_de(user["id"])
if cuat_id is None:
    titulo("user", "Completa tu perfil")
    st.write("Elige tu universidad, carrera y cuatrimestre/semestre.")
    with st.container(border=True):
        sel_perfil = selector_cascada(hasta="cuatrimestre", prefix="perfil", buscar=False)
        if sel_perfil.get("cuatrimestre") and st.button("Guardar perfil", type="primary", icon=":material/save:"):
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
        if sel_nuevo.get("cuatrimestre") and st.button("Guardar cambio", icon=":material/save:"):
            perfil.asignar_cuatrimestre(user["id"], sel_nuevo["cuatrimestre"])
            st.rerun()
    titulo("layers", "Elige tu tema")
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

# si cambia el tema se empieza de cero
for clave in ("conv_id", "conv_ejercicio", "conv_examen", "examen", "examen_resumen", "repaso_resumen", "ejercicio"):
    ss.setdefault(clave, None)
ss.setdefault("intro_hecha", set())  # conversaciones donde el tutor ya saludó o dio la bienvenida de regreso
if ss.get("tema_activo") != tema_id:
    ss.tema_activo = tema_id
    for clave in ("conv_id", "conv_ejercicio", "conv_examen", "examen", "examen_resumen", "repaso_resumen", "ejercicio"):
        ss[clave] = None
    ss.intro_hecha = set()

TIPOS = {"conv_id": "chat", "conv_ejercicio": "ejercicio", "conv_examen": "examen"}


def nueva_conversacion(clave: str, titulo_conv: str) -> int:
    ss[clave] = chat.crear_conversacion(user["id"], tema_id, titulo_conv, TIPOS[clave])
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


# 
# Vista 1: conversación
def _clave_intro(conv_id: int | None) -> str:
    return "nueva" if conv_id is None else f"conv{conv_id}"


def cambiar_conversacion() -> None:
    # Al elegir otra conversación, el tutor vuelve a dar la bienvenida
    ss.conv_id = ss["conv_picker"] or None 
    ss.intro_hecha.discard(_clave_intro(ss.conv_id))


def fragmentos_para(historial: list[dict]) -> list[dict]:
    # Material relacionado con lo último que preguntó el alumno
    preguntas = [m["contenido"] for m in historial if m["rol"] == "user"]
    encontrados = rag.buscar(tema_id, preguntas[-1]) if preguntas else []
    return encontrados or rag.chunks_aleatorios(tema_id, 3)


def accion_tutor(intencion: str, texto_alumno: str | None = None) -> None:
    # El tutor guía la conversación
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
                frags = rag.chunks_aleatorios(tema_id, 3)
                respuesta = tutoria.iniciar_leccion(tema_nombre, tutoria.objetivos_del_tema(tema_id), frags,
                                                    prog["nivel"], "ok" if frags else material.estado_tema(tema_id))
            chat.guardar_mensaje(conv, "assistant", respuesta)
        ss.intro_hecha.update({"nueva", _clave_intro(conv)})
        st.rerun()
    except Exception as e:
        st.error(str(e))


def vista_conversacion() -> None:
    previas = chat.conversaciones_del_tema(user["id"], tema_id)
    etiquetas = {0: "+ Nueva conversación",
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
                if b1.button("Iniciar la lección", type="primary", key="btn_iniciar", icon=":material/play_arrow:"):
                    accion_tutor("iniciar")
                if b2.button("Tengo una pregunta", key="btn_pregunta", icon=":material/help:"):
                    ss.intro_hecha.add("nueva")
                    st.rerun()
            else:
                st.markdown("¡Qué bueno verte de nuevo! Retomamos esta conversación. ¿Qué prefieres?")
                b1, b2, b3 = st.columns(3)
                if b1.button("Retroalimentación", key="btn_retro", icon=":material/rate_review:"):
                    accion_tutor("retro")
                if b2.button("Continuar donde lo dejamos", type="primary", key="btn_continuar",
                             icon=":material/play_arrow:"):
                    accion_tutor("continuar")
                if b3.button("Otra pregunta", key="btn_otra", icon=":material/help:"):
                    ss.intro_hecha.add(_clave_intro(ss.conv_id))
                    st.rerun()
    elif not mensajes:
        st.caption(f"Pregúntame lo que quieras sobre **{tema_nombre}**. También puedes escribir «comencemos».")

    pregunta = st.chat_input("Escribe tu pregunta o «comencemos»…")
    if not pregunta:
        return
    intencion = tutoria.detectar_intencion(pregunta)
    if intencion: 
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


# Vista 2: ejercicio práctico 
def vista_ejercicio() -> None:
    ej = ss.ejercicio
    if ej is None:
        with st.container(border=True):
            st.write(f"Un ejercicio práctico sobre **{tema_nombre}**. "
                     "Lo resuelves a tu ritmo y la IA lo califica de 0 a 10.")
            if st.button("Plantéame un ejercicio", type="primary", icon=":material/edit_note:"):
                try:
                    with st.spinner("Preparando el ejercicio…"):
                        fragmentos = rag.chunks_aleatorios(tema_id, 3)
                        enunciado = llm.responder(tema_nombre, "Plantéame un ejercicio práctico sobre este tema.",
                                                  fragmentos, [], prog["nivel"])
                    if not fragmentos or enunciado == llm.SIN_INFO:
                        st.warning(material.mensaje_sin_material(tema_id))
                        return
                    conv = nueva_conversacion("conv_ejercicio", "Ejercicio práctico")
                    chat.guardar_mensaje(conv, "assistant", enunciado)
                    ss.ejercicio = {"enunciado": enunciado, "fragmentos": fragmentos, "resultado": None}
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        return

    with st.container(border=True):
        st.markdown(ej["enunciado"])
    if ej["resultado"]:
        r = ej["resultado"]
        (st.success if r["puntaje"] >= 6 else st.warning)(
            f"**Calificación: {r['puntaje']}/10**",
            icon=":material/check_circle:" if r["puntaje"] >= 6 else ":material/info:")
        st.markdown(r["retroalimentacion"])
        if st.button("Otro ejercicio", type="primary", icon=":material/refresh:"):
            ss.ejercicio = None
            st.rerun()
        return

    resp_ej = st.text_area("Tu respuesta", key="resp_ejercicio", height=180)
    b1, b2 = st.columns([1, 3])
    if b2.button("Descartar ejercicio", icon=":material/delete:"):
        ss.ejercicio = None
        st.rerun()
    if b1.button("Calificar", type="primary", icon=":material/grading:"):
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


# Vista 3: examen 
def vista_examen_inicio() -> None:
    if ss.examen_resumen:
        st.success("Resultado de tu último examen", icon=":material/check_circle:")
        st.markdown(ss.examen_resumen)
        st.divider()
    inicial = examen.dificultad_inicial(prog["nivel"])
    st.write(f"Examen de varias preguntas sobre **{tema_nombre}**. Empiezas en dificultad "
             f"**{DIFICULTADES[inicial]}** según tu nivel en el tema; mientras aciertes, las preguntas serán más "
             "difíciles, y si fallas bajan un poco.")
    st.info("Durante el examen se oculta todo lo demás (menú y conversación) para que puedas concentrarte. "
            "Después de cada pregunta verás la respuesta correcta y su explicación.")
    with st.container(border=True):
        total = st.number_input("Número de preguntas", min_value=3, max_value=10,
                                value=examen.PREGUNTAS_POR_DEFECTO, step=1)
        if st.button("Comenzar examen", type="primary", icon=":material/play_arrow:"):
            nueva_conversacion("conv_examen", "Examen")
            ss.examen = examen.nuevo_examen(int(total), prog["nivel"])
            ss.examen["xp_inicial"], ss.examen["nivel_inicial"] = estado["xp_efectivo"], estado["nivel"]
            ss.examen["fase"] = "pregunta"
            ss.examen_resumen = None
            st.rerun()


def responder_examen(q: dict, eleccion: int) -> None:
    ex = ss.examen
    r = quiz.evaluar(q["id"], user["id"], eleccion)
    veredicto = ":material/check_circle: ¡Correcto!" if r["es_correcta"] else ":material/cancel: Incorrecto"
    opciones_txt = "\n".join(f"- {LETRAS[i]}) {o}" for i, o in enumerate(q["opciones"]))
    dif = nombre_dificultad(q.get("dificultad"))
    repaso = ex.get("tipo") == "repaso"
    chat.guardar_mensaje(
        ss.conv_examen, "assistant",
        f"**{'Repaso' if repaso else 'Quiz'} {ex['numero']}/{ex['total']}{f' (dificultad {dif})' if dif else ''}:** "
        f"{q['pregunta']}\n\n{opciones_txt}\n\n**Tu respuesta:** {LETRAS[eleccion]} — {veredicto}\n\n"
        f"**Respuesta correcta:** {LETRAS[r['indice_correcto']]}\n\n{r['explicacion']}")
    ex["revision"] = {"numero": ex["numero"], "pregunta": q["pregunta"], "opciones": q["opciones"],
                      "dificultad": q.get("dificultad"), "elegida": eleccion, "correcta": r["indice_correcto"],
                      "acerto": r["es_correcta"], "explicacion": r["explicacion"]}
    examen.registrar_resultado(ex, r["es_correcta"])
    if examen.terminado(ex):
        despues = niveles.estado_tema(user["id"], tema_id)
        base = examen.resumen_repaso(ex) if repaso else examen.resumen_texto(ex)
        resumen = base + "\n\n" + examen.progreso_texto(ex["nivel_inicial"], ex["xp_inicial"], despues)
        chat.guardar_mensaje(ss.conv_examen, "assistant", resumen)
        ss["repaso_resumen" if repaso else "examen_resumen"] = resumen
        ex["fase"] = "final"
    st.rerun()


def vista_examen_en_curso() -> None:
    ex = ss.examen
    contestadas = len(ex["resultados"])
    st.progress(contestadas / ex["total"], text=f"{contestadas} de {ex['total']} respondidas · {tema_nombre}")

    rev = ex.get("revision")
    if rev:  # retroalimentación de la pregunta que acabas de contestar
        d = nombre_dificultad(rev["dificultad"])
        with st.container(border=True):
            st.caption(f"Pregunta {rev['numero']}" + (f" · dificultad {d}" if d and ex.get("tipo") != "repaso" else ""))
            st.markdown(f"**{rev['pregunta']}**")
            for i, o in enumerate(rev["opciones"]):
                opcion_md(i, o, "ok" if i == rev["correcta"] else ("mal" if i == rev["elegida"] else "neutro"))
        if rev["acerto"]:
            st.success("¡Correcto!", icon=":material/check_circle:")
        else:
            st.error(f"Incorrecto. Elegiste {LETRAS[rev['elegida']]}; la correcta era {LETRAS[rev['correcta']]}.",
                     icon=":material/cancel:")
        st.markdown(rev["explicacion"])
        ultimo = examen.terminado(ex)
        if st.button("Ver resultados" if ultimo else "Siguiente pregunta", type="primary",
                     icon=":material/flag:" if ultimo else ":material/arrow_forward:"):
            if ultimo:
                ss.examen = None
            else:
                ex["revision"] = None
            st.rerun()
        return

    if ex["quiz"] is None and ex.get("cola"):  # repaso: se vuelven a plantear las preguntas falladas
        ex["quiz"] = ex["cola"].pop(0)
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
                st.button("Reintentar", icon=":material/refresh:")  # al pulsarlo la página se ejecuta de nuevo
            else:
                st.warning(material.mensaje_sin_material(tema_id))
            if st.button("Salir del examen", icon=":material/logout:"):
                ss.examen = None
                st.rerun()
            return
    q = ex["quiz"]
    d = nombre_dificultad(q.get("dificultad"))
    with st.container(border=True):
        st.caption(f"Pregunta {ex['numero']} de {ex['total']}"
                   + (f" · dificultad {d}" if d and ex.get("tipo") != "repaso" else ""))
        st.markdown(f"### {q['pregunta']}")
        eleccion = st.radio("Elige una opción", range(4), index=None, key=f"quiz_{q['id']}",
                            format_func=lambda i: f"{LETRAS[i]}) {q['opciones'][i]}", label_visibility="collapsed")
    b1, b2 = st.columns([1, 3])
    if b2.button("Abandonar examen", key=f"abandonar_{q['id']}", icon=":material/close:"):
        ss.examen = None
        st.rerun()
    if b1.button("Responder", type="primary", key=f"resp_{q['id']}", icon=":material/send:"):
        if eleccion is None:
            st.warning("Elige una opción primero.")
        else:
            responder_examen(q, eleccion)


def vista_examen() -> None:
    if ss.examen is None:
        vista_examen_inicio()
    else:
        vista_examen_en_curso()


def vista_repaso() -> None:
    if ss.repaso_resumen:
        st.success("Resultado de tu último repaso", icon=":material/check_circle:")
        st.markdown(ss.repaso_resumen)
        st.divider()
    pendientes = quiz.preguntas_pendientes(user["id"], tema_id, 10)
    if not pendientes:
        st.success("No tienes errores pendientes en este tema. ¡Sigue así!", icon=":material/check_circle:")
        st.caption("Aquí aparecen las preguntas que fallaste y que todavía no has contestado bien.")
        return
    st.write(f"Tienes **{len(pendientes)}** pregunta(s) fallada(s) sin corregir en **{tema_nombre}**. "
             "Puedes revisar la respuesta de cada una o practicarlas de nuevo, de a una, sin distracciones.")
    for i, q in enumerate(pendientes, 1):
        with st.expander(f"{i}. {q['pregunta'][:100]}"):
            for j, o in enumerate(q["opciones"]):
                opcion_md(j, o, "ok" if j == q["indice_correcto"] else "neutro")
            st.markdown(q["explicacion"])
    if st.button(f"Practicar mis errores ({min(len(pendientes), 5)})", type="primary", icon=":material/replay:"):
        nueva_conversacion("conv_examen", "Repaso de errores")
        ss.examen = examen.nuevo_repaso(pendientes[:5], prog["nivel"])
        ss.examen["xp_inicial"], ss.examen["nivel_inicial"] = estado["xp_efectivo"], estado["nivel"]
        ss.examen["fase"] = "pregunta"
        ss.repaso_resumen = None
        st.rerun()

# Bloquea para examen
if ss.examen is not None:
    ss["modo_chat"] = MODOS[3] if ss.examen.get("tipo") == "repaso" else MODOS[2]  # al terminar, vuelves a tu pestaña
    vista_examen_en_curso()
else:
    modo = st.radio("Modo", MODOS, horizontal=True, key="modo_chat", label_visibility="collapsed")
    st.divider()
    if modo == MODOS[0]:
        vista_conversacion()
    elif modo == MODOS[1]:
        vista_ejercicio()
    elif modo == MODOS[2]:
        vista_examen()
    else:
        vista_repaso()