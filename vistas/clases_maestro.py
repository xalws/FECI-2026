"""Clases del maestro: crear grupos, compartir el código, aprobar solicitudes y publicar avisos."""
from datetime import datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

from core import boletin, clases, stats, tareas
from core.auth import require_login
from core.estilo import datos, encabezado, fecha_local, insignias, titulo, zona_horaria
from core.estilo import lista as lista_tarjetas
from core.niveles import NOMBRES as NOMBRES_NIVEL
from core.perfil_ui import dialogo_perfil
from core.ui import selector_cascada

user = require_login(["maestro", "admin"])
ss = st.session_state

lista = clases.clases_del_maestro(user["id"])
total_alumnos = sum(c["alumnos"] for c in lista)
pendientes_total = sum(c["pendientes"] for c in lista)
encabezado("Clases", "Separa a tus alumnos por grupo: comparte un código, aprueba solicitudes y publica avisos.",
           "users", chips=[("layers", f"{len(lista)} {'clase' if len(lista) == 1 else 'clases'}"),
                           ("user", f"{total_alumnos} {'alumno' if total_alumnos == 1 else 'alumnos'}")]
           + ([("clock", f"{pendientes_total} por aprobar")] if pendientes_total else []))

# resultado de la acción anterior (se muestra después del st.rerun que la cierra)
aviso = ss.pop("aviso_clases", None)
if aviso:
    st.toast(aviso[0], icon=":material/check_circle:" if aviso[1] else ":material/error:")


def listo(resultado) -> None:
    """Guarda el resultado de una acción para avisarlo y recarga la pantalla."""
    ss["aviso_clases"] = (resultado[1], resultado[0])
    st.rerun()


# ---------------------------------------------------------------------------------------------------------------
# Crear una clase
# ---------------------------------------------------------------------------------------------------------------
materias = clases.materias_para_crear(user["id"])
if not materias:
    st.info("Todavía no tienes materias asignadas. Pídele al administrador que te asigne una para crear tus clases.",
            icon=":material/info:")
    st.stop()

with st.expander("Crear una clase", expanded=not lista, icon=":material/add_circle:"):
    with st.form("form_nueva_clase", clear_on_submit=True, border=False):
        c1, c2 = st.columns([3, 2])
        nombre = c1.text_input("Nombre de la clase", placeholder="Ej. Circuitos Eléctricos · Grupo A", max_chars=clases.MAX_NOMBRE)
        materia_id = c2.selectbox("Materia", list(materias), format_func=materias.get)
        pide_aprobacion = st.checkbox("Aprobar yo a cada alumno que entre con el código", value=True,
                                      help="Si la desmarcas, quien tenga el código entra al instante.")
        if st.form_submit_button("Crear clase", type="primary", icon=":material/add:"):
            ok, msg, nueva = clases.crear_clase(user["id"], materia_id, nombre, pide_aprobacion)
            if ok:
                ss["clase_elegida"] = nueva
            listo((ok, msg))

if not lista:
    st.caption("Cuando crees tu primera clase aparecerá aquí con su código para compartir.")
    st.stop()

datos([{"icono": "layers", "etiqueta": "Clases", "valor": len(lista), "detalle": "grupos creados", "tono": "indigo"},
       {"icono": "users", "etiqueta": "Alumnos", "valor": total_alumnos, "detalle": "dentro de tus clases", "tono": "violeta"},
       {"icono": "clock", "etiqueta": "Por aprobar", "valor": pendientes_total,
        "detalle": "solicitudes pendientes", "tono": "ambar" if pendientes_total else "verde"}])

# ---------------------------------------------------------------------------------------------------------------
# Elegir una clase
# ---------------------------------------------------------------------------------------------------------------
etiquetas = {c["id"]: (f"{c['nombre']} · {c['materia']}" + ("" if c["activa"] else " (desactivada)")
                       + (f" · {c['pendientes']} por aprobar" if c["pendientes"] else "")) for c in lista}
if ss.get("clase_elegida") not in etiquetas:
    ss["clase_elegida"] = lista[0]["id"]
clase_id = st.selectbox("Clase", list(etiquetas), format_func=etiquetas.get, key="clase_elegida")
c = next(x for x in lista if x["id"] == clase_id)

with st.container(border=True, key="tarjeta_clase"):
    col_cod, col_info = st.columns([1, 2], vertical_alignment="center")
    with col_cod:
        st.caption("Código para que tus alumnos se unan")
        st.code(c["codigo"], language=None)
    with col_info:
        titulo("book", c["nombre"], nivel=4)
        insignias((c["materia"], "indigo", "book"),
                  ("Activa" if c["activa"] else "Desactivada", "verde" if c["activa"] else "rojo", "check" if c["activa"] else "x"),
                  ("Con aprobación" if c["aprobacion"] else "Entrada libre", "ambar" if c["aprobacion"] else "cielo", "lock"))
        if user["rol"] == "admin":
            st.caption(f"Maestro: {c['maestro']}")
        st.caption("Los alumnos lo escriben en «Mis clases» > «Unirme con un código».")

t_alumnos, t_solicitudes, t_tareas, t_boletin, t_avisos, t_ajustes = st.tabs([
    f":material/group: Alumnos ({c['alumnos']})", f":material/hourglass_top: Solicitudes ({c['pendientes']})",
    ":material/assignment: Tareas", ":material/summarize: Boletín", ":material/campaign: Avisos", ":material/settings: Ajustes"])

# ----- Alumnos -----
with t_alumnos:
    alumnos = clases.alumnos_de_clase(user["id"], clase_id)
    if not alumnos:
        st.info("Todavía no hay alumnos en esta clase. Comparte el código para que se unan.", icon=":material/group_add:")
    for a in alumnos:
        f1, f2, f3, f4 = st.columns([3, 3, 1.3, 1], vertical_alignment="center")
        f1.markdown(f"**{a['nombre']}**")
        f2.caption(f"{a['email']} · desde {fecha_local(a['fecha']):%d/%m/%Y}")
        if f3.button("Ver perfil", key=f"perfil_{clase_id}_{a['alumno_id']}", icon=":material/badge:", width="stretch"):
            dialogo_perfil(user["id"], a["alumno_id"])
        if f4.button("Quitar", key=f"quitar_{clase_id}_{a['alumno_id']}", icon=":material/person_remove:", width="stretch"):
            listo(clases.quitar_alumno(user["id"], clase_id, a["alumno_id"]))

# ----- Solicitudes -----
with t_solicitudes:
    solicitudes = clases.alumnos_de_clase(user["id"], clase_id, clases.PENDIENTE)
    if not solicitudes:
        st.info("No hay solicitudes pendientes.", icon=":material/inbox:")
    else:
        if len(solicitudes) > 1 and st.button("Aceptar a todos", key=f"aceptar_todos_{clase_id}", type="primary",
                                              icon=":material/done_all:"):
            for s_ in solicitudes:
                clases.resolver_solicitud(user["id"], s_["inscripcion_id"], True)
            listo((True, f"{len(solicitudes)} alumnos aceptados."))
        for s_ in solicitudes:
            f1, f2, f3, f4 = st.columns([3, 3, 1.2, 1.2], vertical_alignment="center")
            f1.markdown(f"**{s_['nombre']}**")
            f2.caption(f"{s_['email']} · pidió entrar el {fecha_local(s_['fecha']):%d/%m/%Y}")
            if f3.button("Aceptar", key=f"si_{s_['inscripcion_id']}", type="primary", icon=":material/check:", width="stretch"):
                listo(clases.resolver_solicitud(user["id"], s_["inscripcion_id"], True))
            if f4.button("Rechazar", key=f"no_{s_['inscripcion_id']}", icon=":material/close:", width="stretch"):
                listo(clases.resolver_solicitud(user["id"], s_["inscripcion_id"], False))

# ----- Tareas -----
with t_tareas:
    zona = zona_horaria()
    with st.container(border=True, key=f"nueva_tarea_{clase_id}"):
        titulo("clipboard", "Asignar una tarea", nivel=4)
        st.caption("Elige un tema de la materia y qué debe lograr cada alumno. Se cumple sola con lo que hacen en «Estudio».")
        sel = selector_cascada(hasta="tema", materias_permitidas=[c["materia_id"]], prefix=f"tarea_{clase_id}", buscar=False)
        tema_id = sel.get("tema")
        k1, k2 = st.columns(2)
        tipo = k1.selectbox("Qué debe hacer", list(tareas.TIPOS), format_func=tareas.TIPOS.get, key=f"tarea_tipo_{clase_id}")
        minimo, maximo, sugerido = tareas.LIMITES[tipo]
        if tipo == "nivel":
            meta = k2.selectbox("Nivel que debe alcanzar", list(range(minimo, maximo + 1)), index=sugerido - minimo,
                                format_func=NOMBRES_NIVEL.get, key=f"tarea_nivel_{clase_id}")
        else:
            meta = k2.number_input("Cuántas" + (" preguntas" if tipo == "preguntas" else " ejercicios"), min_value=minimo,
                                   max_value=maximo, value=sugerido, step=1, key=f"tarea_meta_{tipo}_{clase_id}")
        hoy = datetime.now(zona).date()
        limite = st.date_input("Fecha límite (hasta el final de ese día)", value=hoy + timedelta(days=7), min_value=hoy,
                               format="DD/MM/YYYY", key=f"tarea_fecha_{clase_id}")
        nota = st.text_area("Indicaciones (opcional)", max_chars=tareas.MAX_INSTRUCCIONES, height=80,
                            placeholder="Ej. Repasen sus apuntes antes de empezar.", key=f"tarea_nota_{clase_id}")
        if st.button("Asignar tarea", type="primary", icon=":material/add_task:", disabled=tema_id is None,
                     key=f"tarea_asignar_{clase_id}"):
            fin = datetime.combine(limite, time(23, 59), tzinfo=zona)
            listo(tareas.crear(user["id"], clase_id, tema_id, tipo, int(meta), fin, nota, zona))

    lista_tareas = tareas.tareas_de_clase(user["id"], clase_id)
    if not lista_tareas:
        st.caption("Todavía no has asignado tareas en esta clase. Al asignar una, los alumnos reciben un aviso.")
    else:
        cumplimiento = tareas.matriz(user["id"], clase_id, zona)
        st.download_button("Descargar cumplimiento (Excel)", stats.exportar_excel({"Cumplimiento": cumplimiento}),
                           file_name=f"cumplimiento_{c['nombre']}_{datetime.now(zona):%Y-%m-%d}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/table_view:", key=f"descargar_tareas_{clase_id}")
    ahora = datetime.now(timezone.utc)
    for t in lista_tareas:
        with st.container(border=True):
            f1, f2 = st.columns([6, 1], vertical_alignment="top")
            f1.markdown(f"**{t['descripcion']}** · {t['tema']}")
            f1.caption(f"{tareas.texto_plazo(t['fecha_limite'], ahora, zona).capitalize()} "
                       f"({fecha_local(t['fecha_limite']):%d/%m/%Y})" + (f" · {t['instrucciones']}" if t["instrucciones"] else ""))
            f1.progress(t["hechas"] / t["alumnos"] if t["alumnos"] else 0.0,
                        text=f"{t['hechas']} de {t['alumnos']} alumnos la cumplieron")
            if f2.button("Borrar", key=f"borrar_tarea_{t['id']}", icon=":material/delete:", width="stretch"):
                listo(tareas.eliminar(user["id"], t["id"]))
            with st.expander("Ver avance por alumno"):
                for d in tareas.detalle(user["id"], t["id"]):
                    marca = ":material/check_circle:" if d["hecha"] else ":material/radio_button_unchecked:"
                    st.markdown(f"{marca} **{d['nombre']}** · {d['avance']} de {d['meta']}")

# ----- Boletín semanal -----
TONO_ESTADO = {"Necesita apoyo": "rojo", "Sin actividad": "ambar", "Aún no entra": "ambar", "Destacado": "verde", "Al día": "cielo"}
with t_boletin:
    if not c["alumnos"]:
        st.info("Cuando la clase tenga alumnos verás aquí cómo les fue cada semana.", icon=":material/insights:")
    else:
        b = boletin.generar(user["id"], clase_id, zona_horaria())
        st.caption(f"Últimos 7 días: del {b['desde']:%d/%m} al {b['hasta']:%d/%m}, comparados con la semana anterior.")
        s_, p_ = b["semana"], b["anterior"]
        datos([{"icono": "users", "etiqueta": "Alumnos activos", "valor": f"{s_['activos']} de {b['total_alumnos']}",
                "detalle": f"antes: {p_['activos']}", "tono": "indigo"},
               {"icono": "message", "etiqueta": "Preguntas al tutor", "valor": s_["preguntas"],
                "detalle": f"antes: {p_['preguntas']}", "tono": "violeta"},
               {"icono": "help", "etiqueta": "Quizzes respondidos", "valor": s_["quizzes"],
                "detalle": f"antes: {p_['quizzes']}", "tono": "cielo"},
               {"icono": "target", "etiqueta": "Aciertos", "valor": "—" if s_["aciertos"] is None else f"{s_['aciertos']:.0f}%",
                "detalle": "antes: " + ("—" if p_["aciertos"] is None else f"{p_['aciertos']:.0f}%"), "tono": "verde"}])
        with st.container(border=True):
            titulo("sparkles", "Lo más importante", nivel=4)
            for frase in b["frases"]:
                st.markdown(f"- {frase}")
        if b["necesitan_apoyo"]:
            titulo("flame", "A quién buscar", nivel=4)
            for f in b["necesitan_apoyo"]:
                g1, g2 = st.columns([1.2, 3], vertical_alignment="center")
                with g1:
                    insignias((f["alumno"], TONO_ESTADO[f["estado"]], "user"))
                g2.caption(f"{f['estado']}. {f['motivo']}")
        if b["temas_flojos"]:
            titulo("x", "Temas con más errores", nivel=4)
            lista_tarjetas([{"icono": "x", "titulo": t["tema"], "tono": "rojo",
                             "texto": f"{t['% aciertos']:.0f}% de aciertos en {t['intentos']} respuestas."} for t in b["temas_flojos"]])
        if b["sin_respuesta"]:
            titulo("bulb", "Falta material", nivel=4)
            lista_tarjetas([{"icono": "help", "titulo": d["tema"], "tono": "ambar",
                             "texto": f"El tutor no pudo contestar {d['preguntas']} {'pregunta' if d['preguntas'] == 1 else 'preguntas'}."}
                            for d in b["sin_respuesta"]])
        if b["tareas"]:
            titulo("clipboard", "Tareas de la semana", nivel=4)
            lista_tarjetas([{"icono": "clipboard", "titulo": t["tarea"], "sub": t["tema"], "tono": "ambar" if not t["vencida"] else "rojo",
                             "texto": f"{'Venció' if t['vencida'] else 'Vence'} el {t['límite']:%d/%m/%Y}. La cumplieron {t['hechas']} de {t['alumnos']}."}
                            for t in b["tareas"]])
        with st.expander("Todos los alumnos", icon=":material/table_rows:"):
            tabla = pd.DataFrame(b["alumnos"]).drop(columns="motivo").rename(columns={"aciertos": "% aciertos"})
            st.dataframe(tabla, hide_index=True)
        d1, d2 = st.columns(2)
        d1.download_button("Texto para enviar", boletin.como_texto(b).encode("utf-8"), icon=":material/notes:",
                           file_name=f"boletin_{c['nombre']}_{b['hasta']:%Y-%m-%d}.txt".replace(" ", "_"),
                           mime="text/plain", width="stretch", key=f"boletin_txt_{clase_id}")
        d2.download_button("Boletín (Excel)", boletin.como_excel(b), icon=":material/table_view:", type="primary",
                           file_name=f"boletin_{c['nombre']}_{b['hasta']:%Y-%m-%d}.xlsx".replace(" ", "_"),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           width="stretch", key=f"boletin_xlsx_{clase_id}")

# ----- Avisos -----
with t_avisos:
    with st.form(f"form_aviso_{clase_id}", clear_on_submit=True, border=False):
        texto = st.text_area("Nuevo aviso para la clase", max_chars=clases.MAX_AVISO, height=100,
                             placeholder="Ej. El examen de la unidad 1 será el viernes. Repasen «Leyes de Kirchhoff».")
        if st.form_submit_button("Publicar aviso", type="primary", icon=":material/campaign:"):
            listo(clases.publicar_aviso(user["id"], clase_id, texto))
    avisos = clases.avisos_de_clase(user["id"], clase_id)
    if not avisos:
        st.caption("Todavía no has publicado avisos en esta clase.")
    for a in avisos:
        with st.container(border=True):
            f1, f2 = st.columns([6, 1], vertical_alignment="top")
            f1.markdown(a["texto"])
            f1.caption(f"Publicado el {fecha_local(a['fecha']):%d/%m/%Y a las %H:%M}")
            if f2.button("Borrar", key=f"borrar_aviso_{a['id']}", icon=":material/delete:", width="stretch"):
                listo(clases.borrar_aviso(user["id"], a["id"]))

# ----- Ajustes -----
with t_ajustes:
    with st.form(f"form_ajustes_{clase_id}", border=False):
        nuevo_nombre = st.text_input("Nombre de la clase", value=c["nombre"], max_chars=clases.MAX_NOMBRE)
        activa = st.toggle("Clase activa", value=c["activa"], help="Si la desactivas, nadie nuevo puede unirse y sus "
                           "avisos dejan de mostrarse a los alumnos. No se borra nada.")
        aprobacion = st.toggle("Aprobar yo a cada alumno que entre con el código", value=c["aprobacion"])
        if st.form_submit_button("Guardar cambios", type="primary", icon=":material/save:"):
            listo(clases.actualizar(user["id"], clase_id, nombre=nuevo_nombre, activa=activa, aprobacion=aprobacion))

    st.divider()
    titulo("key", "Código de la clase", nivel=4)
    st.caption("Si el código se compartió con quien no debía, cámbialo: el anterior deja de servir. Los alumnos que ya "
               "están dentro no se afectan.")
    if st.button("Generar un código nuevo", key=f"codigo_{clase_id}", icon=":material/autorenew:"):
        ok, resultado = clases.nuevo_codigo(user["id"], clase_id)
        listo((ok, f"Código nuevo: {resultado}" if ok else resultado))

    st.divider()
    titulo("x", "Eliminar la clase", nivel=4)
    st.caption("Se borran la clase, sus tareas, sus avisos y la lista de alumnos. El progreso de los alumnos no se toca. "
               "No se puede deshacer.")
    seguro = st.checkbox("Entiendo que se eliminará esta clase", key=f"seguro_{clase_id}")
    if st.button("Eliminar clase", key=f"eliminar_{clase_id}", icon=":material/delete_forever:", disabled=not seguro):
        listo(clases.eliminar_clase(user["id"], clase_id))
