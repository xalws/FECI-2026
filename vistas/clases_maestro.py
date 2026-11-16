"""Clases del maestro: crear grupos, compartir el código, aprobar solicitudes y publicar avisos."""
import streamlit as st

from core import clases
from core.auth import require_login
from core.estilo import datos, encabezado, fecha_local, insignias, titulo

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

t_alumnos, t_solicitudes, t_avisos, t_ajustes = st.tabs([
    f":material/group: Alumnos ({c['alumnos']})", f":material/hourglass_top: Solicitudes ({c['pendientes']})",
    ":material/campaign: Avisos", ":material/settings: Ajustes"])

# ----- Alumnos -----
with t_alumnos:
    alumnos = clases.alumnos_de_clase(user["id"], clase_id)
    if not alumnos:
        st.info("Todavía no hay alumnos en esta clase. Comparte el código para que se unan.", icon=":material/group_add:")
    for a in alumnos:
        f1, f2, f3 = st.columns([3, 3, 1], vertical_alignment="center")
        f1.markdown(f"**{a['nombre']}**")
        f2.caption(f"{a['email']} · desde {fecha_local(a['fecha']):%d/%m/%Y}")
        if f3.button("Quitar", key=f"quitar_{clase_id}_{a['alumno_id']}", icon=":material/person_remove:", width="stretch"):
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
    st.caption("Se borran la clase, sus avisos y la lista de alumnos. El progreso de los alumnos no se toca. "
               "No se puede deshacer.")
    seguro = st.checkbox("Entiendo que se eliminará esta clase", key=f"seguro_{clase_id}")
    if st.button("Eliminar clase", key=f"eliminar_{clase_id}", icon=":material/delete_forever:", disabled=not seguro):
        listo(clases.eliminar_clase(user["id"], clase_id))
