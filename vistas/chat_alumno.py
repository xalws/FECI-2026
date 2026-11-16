import streamlit as st

from core import chat, clases, examen, llm, logros, material, niveles, perfil, progreso, quiz, rag, tutoria
from core.auth import require_login
from core.estudiante import cargando
from core.hoy import panel_estudio as panel_dia
from core.tareas_ui import resumen_estudio as resumen_tareas
from core.estilo import (confeti, datos, encabezado, fecha_local, reanimar, reanimar_siguientes, saludo, svg,
                         titulo, zona_horaria)
from core.llm import DIFICULTADES
from core.ui import error_ia, nombre_tema, selector_cascada

user = require_login(["alumno"])
ss = st.session_state

# Los modos usan iconos Material dentro de la etiqueta (el resto del código los usa por índice)
MODOS = [":material/chat: Conversación", ":material/edit_note: Ejercicio práctico",
         ":material/assignment: Examen", ":material/replay: Repasar errores"]
LETRAS = "ABCD"

# Colores de las opciones revisadas (los íconos y los estilos vienen de core/estilo.py)
COLOR_OK, COLOR_MAL, COLOR_NEUTRO = "#059669", "#DC2626", "#94A3B8"


def opcion_md(i: int, texto: str, estado: str) -> None:
    """Opción de quiz con ícono: estado = 'ok' | 'mal' | 'neutro'."""
    color = {"ok": COLOR_OK, "mal": COLOR_MAL}.get(estado, COLOR_NEUTRO)
    icono = {"ok": "check", "mal": "x"}.get(estado, "circle")
    clase = ' class="tu-marca"' if estado in ("ok", "mal") else ""  # la palomita y el tache aparecen con un «pop»
    marca = (f'<span{clase} style="display:inline-flex;vertical-align:-3px;margin-right:6px">'
             f'{svg(icono, 18, color, 2.2)}</span>')
    st.markdown(f"{marca}**{LETRAS[i]})** {texto}", unsafe_allow_html=True)


# Avisos y festejos pendientes de la acción anterior (se muestran después del st.rerun que la cierra)
aviso = ss.pop("aviso", None)
if aviso:
    st.toast(aviso[0], icon=aviso[1])
if ss.pop("celebrar", False):
    st.balloons()
if ss.pop("revisar_logros", False) or "logros_vistos" not in ss:  # la primera vez solo toma nota
    logros.revisar_nuevos(user["id"], zona_horaria())
if ss.pop("confeti", False):  # (después de revisar logros: subir a Oro también lanza confeti)
    confeti()


@st.cache_data(ttl=30, show_spinner=False)
def _avisos_recientes(alumno_id: int) -> list[dict]:
    return clases.avisos_para_alumno(alumno_id, dias=14, limite=3)


def mostrar_avisos() -> None:
    """Últimos avisos de las clases del alumno, arriba de Estudio."""
    avisos = _avisos_recientes(user["id"])
    if not avisos:
        return
    with st.container(border=True, key="avisos_clase"):
        titulo("bulb", "Avisos de tus clases", nivel=4)
        for a in avisos:
            st.markdown(f"**{a['clase']}** · {a['texto']}")
            st.caption(f"{a['autor']} · {fecha_local(a['fecha']):%d/%m/%Y %H:%M}")
        st.page_link("vistas/clases_alumno.py", label="Ver mis clases", icon=":material/groups:")


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
# El encabezado se llena más abajo, cuando ya se sabe el tema y el nivel. Es un contenedor y no st.empty():
# así se actualiza en su lugar y no vuelve a entrar animado con cada clic.
cabecera = st.container()

cuat_id = perfil.cuatrimestre_de(user["id"])
if cuat_id is None:
    with cabecera:
        encabezado("Completa tu perfil", "Elige tu universidad, carrera y cuatrimestre/semestre para ver tus materias.",
                   "user")
    with st.container(border=True):
        sel_perfil = selector_cascada(hasta="cuatrimestre", prefix="perfil", buscar=False)
        if sel_perfil.get("cuatrimestre") and st.button("Guardar perfil", type="primary", icon=":material/save:"):
            perfil.asignar_cuatrimestre(user["id"], sel_perfil["cuatrimestre"])
            st.rerun()
    st.stop()

def bloque_academico() -> None:
    """Universidad, carrera y cuatrimestre del alumno, con la opción de cambiarlos (va debajo de la barra de XP)."""
    st.divider()
    datos_acad = perfil.datos_academicos(cuat_id)
    if datos_acad:
        st.caption(" · ".join(datos_acad))
    with st.expander("Cambiar mi universidad / carrera / cuatrimestre"):
        sel_nuevo = selector_cascada(hasta="cuatrimestre", prefix="cambiar_perfil", buscar=False)
        if sel_nuevo.get("cuatrimestre") and st.button("Guardar cambio", icon=":material/save:"):
            perfil.asignar_cuatrimestre(user["id"], sel_nuevo["cuatrimestre"])
            st.rerun()


with st.sidebar:
    st.divider()
    titulo("layers", "Elige tu tema")
    materias_clase = clases.materias_del_alumno(user["id"])
    opciones_ver = ["Mi cuatrimestre"] + (["Mis clases"] if materias_clase else []) + ["Todas las materias"]
    if ss.get("ver_materias") not in opciones_ver:  # primera vez, o ya no está en ninguna clase
        ss["ver_materias"] = "Mis clases" if materias_clase else "Mi cuatrimestre"
    ver = st.radio("Materias a mostrar", opciones_ver, key="ver_materias",
                   help="«Mis clases» muestra las materias de las clases donde tu maestro ya te aceptó. Con «Todas las "
                        "materias» puedes estudiar una que no sea de tu cuatrimestre.")
    if ver == "Mi cuatrimestre":
        sel = selector_cascada(hasta="tema", prefix="chat", cuatrimestre_id=cuat_id)
    elif ver == "Mis clases":
        sel = selector_cascada(hasta="tema", prefix="chat_clases", materias_permitidas=materias_clase)
    else:
        sel = selector_cascada(hasta="tema", prefix="chat_todas")
tema_id = sel.get("tema")
if tema_id is None:
    with cabecera:
        encabezado(saludo(user["nombre"]), "Elige una materia y un tema en el menú de la izquierda para empezar.", "book")
    st.info("Elige materia, unidad y tema en el menú de la izquierda para empezar.", icon=":material/arrow_back:")
    with st.sidebar:
        bloque_academico()
    st.stop()
tema_nombre = nombre_tema(tema_id)
prog = progreso.progreso_tema(user["id"], tema_id)
NIVELES = {"apoyo": "refuerzo", "normal": "normal", "avanzado": "avanzado"}
estado = niveles.estado_tema(user["id"], tema_id)

xp_texto = (f"{estado['xp_efectivo']}/{estado['siguiente_xp']} XP para subir" if estado["siguiente_xp"]
            else f"{estado['xp_efectivo']} XP · nivel máximo")
with cabecera:
    if en_examen:
        repaso_activo = ss.examen.get("tipo") == "repaso"
        encabezado("Repaso de errores" if repaso_activo else "Examen", tema_nombre,
                   "refresh" if repaso_activo else "clipboard", compacto=True,
                   chips=[("target", f"{len(ss.examen['resultados'])} de {ss.examen['total']} respondidas"),
                          ("shield", "Modo concentración")])
    else:
        encabezado(saludo(user["nombre"]), f"Estás estudiando: {tema_nombre}", "book",
                   chips=[("award", f"Nivel {estado['nivel']} · {estado['nombre_nivel']}"), ("zap", xp_texto),
                          ("sparkles", f"Modo {NIVELES[prog['nivel']]}")])
if not en_examen:
    mostrar_avisos()
    panel_dia(user["id"])
    resumen_tareas(user["id"])
with st.sidebar:
    if prog["total"]:
        st.caption(f"Tu progreso en este tema: {prog['aciertos']}/{prog['total']} aciertos "
                   f"({prog['porcentaje']}%) · modo {NIVELES[prog['nivel']]}")
    else:
        st.caption("Aún no has respondido quizzes de este tema.")
    siguiente = f"{estado['xp_efectivo']}/{estado['siguiente_xp']} XP" if estado["siguiente_xp"] else "nivel máximo"
    st.progress(estado["porcentaje"] / 100,
                text=f"Nivel del tema: {estado['nivel']} · {estado['nombre_nivel']} ({siguiente})")
    bloque_academico()

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
        with cargando("Pensando…"):
            conv = ss.conv_id or nueva_conversacion(
                "conv_id", f"Lección: {tema_nombre}" if intencion == "iniciar" else (texto_alumno or "Conversación"))
            historial = chat.listar_mensajes(conv)
            if texto_alumno:
                chat.guardar_mensaje(conv, "user", texto_alumno)
            if intencion == "saludo":
                respuesta = tutoria.SALUDO.format(tema=tema_nombre)
            elif intencion == "retro":
                respuesta = tutoria.retroalimentar(tema_nombre, historial, fragmentos_para(historial))
            elif intencion == "resumen":
                respuesta = tutoria.resumir_tema(tema_nombre, tutoria.objetivos_del_tema(tema_id),
                                                 rag.chunks_aleatorios(tema_id, 8), prog["nivel"])
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
        error_ia(e)


def vista_conversacion() -> None:
    previas = chat.conversaciones_del_tema(user["id"], tema_id)
    etiquetas = {0: "+ Nueva conversación",
                 **{c["id"]: f"{fecha_local(c['fecha']):%d/%m %H:%M} · {c['titulo'][:38]}" for c in previas}}
    if ss.conv_id and ss.conv_id not in etiquetas:
        etiquetas[ss.conv_id] = "Conversación actual"
    ss["conv_picker"] = ss.conv_id or 0  # sincroniza el selector antes de crearlo
    st.selectbox("Conversación", list(etiquetas), format_func=etiquetas.get, key="conv_picker",
                 on_change=cambiar_conversacion, label_visibility="collapsed")

    pregunta = st.chat_input("Escribe tu pregunta o «comencemos»…")  # se lee antes para limpiar errores viejos
    pregunta = pregunta or ss.pop("pregunta_rapida", None)  # o la que eligió con un botón bajo la respuesta
    if pregunta:
        ss.pop("fallo_ia", None)

    mensajes = chat.listar_mensajes(ss.conv_id) if ss.conv_id else []
    for m in mensajes:
        with st.chat_message(m["rol"]):
            st.markdown(m["contenido"])

    # Error pendiente de la respuesta anterior: se muestra en cada ejecución para que «Reintentar» funcione
    fallo = ss.get("fallo_ia")
    reintento = None
    if fallo and fallo["conv"] == ss.conv_id and not pregunta:
        with st.chat_message("assistant"):
            if error_ia(fallo["error"], "pregunta"):
                reintento = fallo["pregunta"]
                ss.pop("fallo_ia", None)

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

    # Atajos bajo la última respuesta del tutor: lo mismo que escribir esa frase corta en el chat
    if (mensajes and mensajes[-1]["rol"] == "assistant" and not fallo and not pregunta
            and _clave_intro(ss.conv_id) in ss.intro_hecha):
        atajos = [("Explícamelo más simple", ":material/lightbulb:"), ("Dame un ejemplo", ":material/science:"),
                  ("Hazme una pregunta", ":material/quiz:"), ("Resumen del tema", ":material/summarize:")]
        for col, (texto, icono) in zip(st.columns(len(atajos)), atajos):
            if col.button(texto, key=f"atajo_{ss.conv_id}_{len(mensajes)}_{texto}", icon=icono, width="stretch"):
                ss["pregunta_rapida"] = texto
                st.rerun()

    if not pregunta and not reintento:
        return
    if reintento:  # la pregunta ya quedó guardada: solo se vuelve a pedir la respuesta
        pregunta, conv = reintento, ss.conv_id
        historial = chat.listar_mensajes(conv)[:-1]  # sin la pregunta que se reintenta (último mensaje)
    else:
        intencion = tutoria.detectar_intencion(pregunta)
        if intencion:
            accion_tutor(intencion, pregunta)
            return
        conv = ss.conv_id or nueva_conversacion("conv_id", pregunta)
        ss.intro_hecha.update({"nueva", _clave_intro(conv)})
        historial = chat.listar_mensajes(conv)
    if not reintento:  # la pregunta aparece al instante, antes de buscar en el material
        chat.guardar_mensaje(conv, "user", pregunta)
        with st.chat_message("user"):
            st.markdown(pregunta)
    with st.chat_message("assistant"):
        lugar = st.empty()
        lugar.markdown("Pensando…")
        escrito = ""
        try:
            fragmentos = rag.buscar(tema_id, tutoria.consulta_de_busqueda(historial, pregunta))
            if not fragmentos and tutoria.es_seguimiento(historial, pregunta):
                fragmentos = rag.chunks_aleatorios(tema_id, 3)  # «como?»: que el tutor decida con la conversación
            # la respuesta se muestra conforme el modelo la va escribiendo
            for trozo in llm.responder_en_vivo(tema_nombre, pregunta, fragmentos, historial, prog["nivel"]):
                escrito += trozo
                lugar.markdown(llm._formato_latex(escrito) + " ▍")
            respuesta = llm._formato_latex(escrito.strip())
            if respuesta != llm.SIN_INFO:
                respuesta += texto_fuentes(fragmentos)
            else:
                chat.registrar_sin_respuesta(user["id"], tema_id, pregunta)
            lugar.markdown(respuesta)
            chat.guardar_mensaje(conv, "assistant", respuesta)
            st.rerun()  # se vuelve a dibujar con los atajos (más simple, ejemplo, pregunta, resumen) bajo la respuesta nueva
        except Exception as e:
            lugar.empty()
            ss["fallo_ia"] = {"error": e, "pregunta": pregunta, "conv": conv}
            st.rerun()  # el error y su botón «Reintentar» se dibujan en la ejecución siguiente


# Vista 2: ejercicio práctico 
def vista_ejercicio() -> None:
    ej = ss.ejercicio
    if ej is None:
        with st.container(border=True):
            titulo("bulb", "Ejercicio práctico", nivel=4)
            st.write(f"Un ejercicio práctico sobre **{tema_nombre}**. "
                     "Lo resuelves a tu ritmo y la IA lo califica de 0 a 10.")
            if st.button("Plantéame un ejercicio", type="primary", icon=":material/edit_note:", key="cta_ejercicio"):
                try:
                    with cargando("Preparando el ejercicio…"):
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
                    error_ia(e)
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
            with cargando("Calificando…"):
                r = llm.calificar_ejercicio(ej["enunciado"], resp_ej, ej["fragmentos"])
            progreso.guardar_intento(user["id"], tema_id, ej["enunciado"], resp_ej, r["puntaje"], r["retroalimentacion"])
            chat.guardar_mensaje(ss.conv_ejercicio, "user", f"**Mi respuesta al ejercicio:**\n\n{resp_ej}")
            chat.guardar_mensaje(ss.conv_ejercicio, "assistant",
                                 f"**Calificación: {r['puntaje']}/10**\n\n{r['retroalimentacion']}")
            ej["resultado"] = r
            ss["aviso"] = (f"Calificación: {r['puntaje']}/10", ":material/grading:")
            ss["revisar_logros"] = True
            if r["puntaje"] >= 9:
                ss["celebrar"] = True  # globos: calificación sobresaliente
            st.rerun()
        except Exception as e:
            error_ia(e)


# Vista 3: examen 
def vista_examen_inicio() -> None:
    if ss.examen_resumen:
        with st.container(border=True):
            titulo("award", "Resultado de tu último examen", nivel=4)
            st.markdown(ss.examen_resumen)
    inicial = examen.dificultad_inicial(prog["nivel"])
    titulo("clipboard", f"Examen de {tema_nombre}")
    datos([{"icono": "target", "etiqueta": "Empiezas en dificultad", "valor": DIFICULTADES[inicial].capitalize(),
            "detalle": "según tu nivel en el tema", "tono": "indigo"},
           {"icono": "trending", "etiqueta": "Si aciertas", "valor": "Sube",
            "detalle": "la siguiente pregunta es más difícil", "tono": "verde"},
           {"icono": "refresh", "etiqueta": "Si fallas", "valor": "Baja",
            "detalle": "y ves la explicación al momento", "tono": "ambar"},
           {"icono": "shield", "etiqueta": "Modo concentración", "valor": "Activo",
            "detalle": "se oculta el menú y el chat", "tono": "violeta"}])
    with st.container(border=True):
        total = st.number_input("Número de preguntas", min_value=3, max_value=10,
                                value=examen.PREGUNTAS_POR_DEFECTO, step=1)
        if st.button("Comenzar examen", type="primary", icon=":material/play_arrow:", key="cta_examen"):
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
    ss["revisar_logros"] = True
    puntos = (q.get("dificultad") or 2) if r["es_correcta"] else 0
    ss["aviso"] = ((f"¡Correcto! +{puntos} XP", ":material/celebration:") if r["es_correcta"]
                   else ("Casi: revisa la explicación y sigue", ":material/lightbulb:"))
    if examen.terminado(ex):
        despues = niveles.estado_tema(user["id"], tema_id)
        base = examen.resumen_repaso(ex) if repaso else examen.resumen_texto(ex)
        resumen = base + "\n\n" + examen.progreso_texto(ex["nivel_inicial"], ex["xp_inicial"], despues)
        chat.guardar_mensaje(ss.conv_examen, "assistant", resumen)
        ss["repaso_resumen" if repaso else "examen_resumen"] = resumen
        ex["fase"] = "final"
        aciertos = sum(1 for res in ex["resultados"] if res["acerto"])
        if despues["nivel"] > ex["nivel_inicial"]:  # subió de nivel: globos
            ss["celebrar"] = True
            ss["aviso"] = (f"¡Subiste a nivel {despues['nivel']} · {despues['nombre_nivel']}!", ":material/military_tech:")
        elif aciertos / len(ex["resultados"]) >= 0.8:  # terminó con 80% o más: globos
            ss["celebrar"] = True
    st.rerun()


def vista_examen_en_curso() -> None:
    ex = ss.examen
    contestadas = len(ex["resultados"])
    st.progress(contestadas / ex["total"], text=f"{contestadas} de {ex['total']} respondidas · {tema_nombre}")

    rev = ex.get("revision")
    if rev:  # retroalimentación de la pregunta que acabas de contestar
        d = nombre_dificultad(rev["dificultad"])
        reanimar("tarjeta_revision", rev["numero"], "voltear", 0.7)  # la tarjeta «se voltea» para mostrar la respuesta
        with st.container(border=True, key="tarjeta_revision"):
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
        error = None
        try:
            with cargando("Preparando la pregunta…"):
                ex["quiz"] = quiz.crear_quiz(tema_id, ss.conv_examen, ex["dificultad"], user["id"])
        except Exception as e:
            error = e
        if ex["quiz"] is None:
            if error:
                error_ia(error, "pregunta_examen")  # al pulsar «Reintentar» la página se ejecuta de nuevo
            else:
                st.warning(material.mensaje_sin_material(tema_id))
            if st.button("Salir del examen", icon=":material/logout:"):
                ss.examen = None
                st.rerun()
            return
    q = ex["quiz"]
    d = nombre_dificultad(q.get("dificultad"))
    reanimar("tarjeta_pregunta", q["id"], "der")  # cada pregunta nueva entra deslizándose
    with st.container(border=True, key="tarjeta_pregunta"):
        st.caption(f"Pregunta {ex['numero']} de {ex['total']}"
                   + (f" · dificultad {d}" if d and ex.get("tipo") != "repaso" else ""))
        st.markdown(f"### {q['pregunta']}")
        eleccion = st.radio("Elige una opción", range(4), index=None, key=f"quiz_{q['id']}", width="stretch",
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
        with st.container(border=True):
            titulo("award", "Resultado de tu último repaso", nivel=4)
            st.markdown(ss.repaso_resumen)
    pendientes = quiz.preguntas_pendientes(user["id"], tema_id, 10)
    if not pendientes:
        st.success("No tienes errores pendientes en este tema. ¡Sigue así!", icon=":material/check_circle:")
        st.caption("Aquí aparecen las preguntas que fallaste y que todavía no has contestado bien.")
        return
    titulo("refresh", "Tus errores por corregir")
    a_practicar = min(len(pendientes), 5)
    datos([{"icono": "target", "etiqueta": "Preguntas por corregir", "valor": len(pendientes),
            "detalle": f"en {tema_nombre}", "tono": "ambar"},
           {"icono": "zap", "etiqueta": "Práctica de hoy",
            "valor": f"{a_practicar} {'pregunta' if a_practicar == 1 else 'preguntas'}",
            "detalle": "una por una, sin distracciones", "tono": "indigo"}])
    st.caption("Abre cada pregunta para ver la respuesta correcta, o practícalas de nuevo con el botón de abajo.")
    for i, q in enumerate(pendientes, 1):
        with st.expander(f"{i}. {q['pregunta'][:100]}"):
            for j, o in enumerate(q["opciones"]):
                opcion_md(j, o, "ok" if j == q["indice_correcto"] else "neutro")
            st.markdown(q["explicacion"])
    if st.button(f"Practicar mis errores ({a_practicar})", type="primary", icon=":material/replay:", key="cta_repaso"):
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
    reanimar_siguientes("modo_chat", MODOS.index(modo))  # al cambiar de pestaña, su contenido entra animado
    st.write("")
    if modo == MODOS[0]:
        vista_conversacion()
    elif modo == MODOS[1]:
        vista_ejercicio()
    elif modo == MODOS[2]:
        vista_examen()
    else:
        vista_repaso()