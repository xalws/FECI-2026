"""Tareas del maestro: programar tareas nuevas, editarlas, reprogramar fechas y publicarlas cuando convenga."""
from datetime import date, datetime, time, timedelta, timezone

import streamlit as st

from core import clases, reticula, tareas
from core.auth import require_login
from core.estilo import encabezado, fecha_local, insignias, titulo, zona_horaria
from core.niveles import NOMBRES as NOMBRES_NIVEL

user = require_login(["maestro", "admin"])
ss = st.session_state
zona = zona_horaria()
ahora = datetime.now(timezone.utc)

HORA_LIMITE = time(23, 59)    # por defecto una tarea vence al final del día
HORA_PUBLICACION = time(8, 0)  # y una tarea programada se publica a primera hora

lista_clases = clases.clases_del_maestro(user["id"])
todas = tareas.del_maestro(user["id"])
programadas = sum(1 for t in todas if t["programada"])
vigentes = sum(1 for t in todas if not t["programada"] and not t["vencida"])
encabezado("Tareas", "Programa tareas con fecha de publicación y de entrega; edítalas o reprograma sus fechas cuando quieras.",
           "clipboard", chips=[("clipboard", f"{vigentes} vigentes"), ("clock", f"{programadas} programadas"),
                               ("layers", f"{len(lista_clases)} {'clase' if len(lista_clases) == 1 else 'clases'}")])

aviso = ss.pop("aviso_tareas", None)
if aviso:
    st.toast(aviso[0], icon=":material/check_circle:" if aviso[1] else ":material/error:")


def listo(resultado) -> None:
    ss["aviso_tareas"] = (resultado[1], resultado[0])
    st.rerun()


def _fecha_hora(prefijo: str, etiqueta: str, valor: datetime | None, hora_defecto: time, minimo: date,
                ayuda: str | None = None) -> datetime:
    """Selector de día y hora (en la hora local del maestro). Devuelve la fecha ya con zona horaria."""
    local = fecha_local(valor) if valor else None
    c1, c2 = st.columns([3, 2])
    dia = c1.date_input(etiqueta, value=local.date() if local else minimo, min_value=min(minimo, local.date()) if local else minimo,
                        format="DD/MM/YYYY", key=f"{prefijo}_dia", help=ayuda)
    hora = c2.time_input("Hora", value=local.time().replace(second=0, microsecond=0) if local else hora_defecto,
                         key=f"{prefijo}_hora", step=300)
    return datetime.combine(dia, hora, tzinfo=zona)


def _campos(prefijo: str, materia_id: int, valores: dict | None = None):
    """Los campos de una tarea (nueva o existente). Devuelve (tema_id, tipo, meta, limite, nota, publicar)."""
    v = valores or {}
    temas = reticula.temas_de_materia(materia_id)
    etiquetas = {t["id"]: f"{t['unidad']} › {t['nombre']}" for t in temas}
    ids = list(etiquetas)
    tema_id = st.selectbox("Tema", ids, index=ids.index(v["tema_id"]) if v.get("tema_id") in ids else 0,
                           format_func=etiquetas.get, key=f"{prefijo}_tema")
    k1, k2 = st.columns(2)
    tipo = k1.selectbox("Qué debe hacer", list(tareas.TIPOS), format_func=tareas.TIPOS.get, key=f"{prefijo}_tipo",
                        index=list(tareas.TIPOS).index(v["tipo"]) if v.get("tipo") else 0)
    minimo, maximo, sugerido = tareas.LIMITES[tipo]
    meta_previa = v.get("meta") if v.get("tipo") == tipo else sugerido
    if tipo == "nivel":
        meta = k2.selectbox("Nivel que debe alcanzar", list(range(minimo, maximo + 1)), index=(meta_previa or sugerido) - minimo,
                            format_func=NOMBRES_NIVEL.get, key=f"{prefijo}_nivel")
    else:
        meta = k2.number_input("Cuántas" + (" preguntas" if tipo == "preguntas" else " ejercicios"), min_value=minimo,
                               max_value=maximo, value=int(meta_previa or sugerido), step=1, key=f"{prefijo}_meta_{tipo}")
    hoy = datetime.now(zona).date()
    limite = _fecha_hora(f"{prefijo}_limite", "Fecha límite de entrega", v.get("fecha_limite") or datetime.combine(
        hoy + timedelta(days=7), HORA_LIMITE, tzinfo=zona).astimezone(timezone.utc), HORA_LIMITE, hoy)
    programada = bool(v.get("programada"))
    modo = st.radio("Publicación", ["Publicar ahora", "Programar la publicación"], horizontal=True, key=f"{prefijo}_modo",
                    index=1 if programada else 0,
                    help="Una tarea programada no la ven los alumnos (ni su aviso) hasta la fecha que elijas. "
                         "Cuenta lo que hagan desde entonces.")
    publicar = None
    if modo == "Programar la publicación":
        base = v.get("visible_desde") if programada else datetime.combine(hoy + timedelta(days=1), HORA_PUBLICACION, tzinfo=zona)
        publicar = _fecha_hora(f"{prefijo}_pub", "Publicar el", base, HORA_PUBLICACION, hoy)
    nota = st.text_area("Indicaciones (opcional)", value=v.get("instrucciones", ""), max_chars=tareas.MAX_INSTRUCCIONES,
                        height=80, placeholder="Ej. Repasen sus apuntes antes de empezar.", key=f"{prefijo}_nota")
    return tema_id, tipo, int(meta), limite, nota, publicar


# ---------------------------------------------------------------------------------------------------------------
# Programar una tarea nueva
# ---------------------------------------------------------------------------------------------------------------
if not lista_clases:
    st.info("Todavía no tienes clases. Crea una para poder asignarle tareas.", icon=":material/info:")
    st.page_link("vistas/clases_maestro.py", label="Ir a Clases", icon=":material/groups:")
    st.stop()

etiquetas_clase = {c["id"]: f"{c['nombre']} · {c['materia']}" + ("" if c["activa"] else " (desactivada)") for c in lista_clases}
with st.expander("Programar una tarea nueva", expanded=not todas, icon=":material/add_task:"):
    clase_id = st.selectbox("Clase", list(etiquetas_clase), format_func=etiquetas_clase.get, key="nueva_clase")
    clase = next(c for c in lista_clases if c["id"] == clase_id)
    tema_id, tipo, meta, limite, nota, publicar = _campos(f"nt_{clase_id}", clase["materia_id"])
    if st.button("Programar tarea" if publicar else "Asignar tarea", type="primary", icon=":material/add_task:",
                 key=f"nt_guardar_{clase_id}"):
        listo(tareas.crear(user["id"], clase_id, tema_id, tipo, meta, limite, nota, zona, publicar)[:2])


# ---------------------------------------------------------------------------------------------------------------
# Editar o reprogramar
# ---------------------------------------------------------------------------------------------------------------
@st.dialog("Editar tarea", width="large")
def editar_tarea(t: dict) -> None:
    st.caption(f"{t['clase']} · {t['materia']}. Lo que los alumnos ya hicieron se conserva, y su aviso en la clase se actualiza.")
    tema_id, tipo, meta, limite, nota, publicar = _campos(f"et_{t['id']}", t["materia_id"], t)
    b1, b2 = st.columns(2)
    if b1.button("Guardar cambios", type="primary", icon=":material/save:", width="stretch", key=f"et_ok_{t['id']}"):
        listo(tareas.editar(user["id"], t["id"], tema_id, tipo, meta, limite, nota, zona, publicar))
    if b2.button("Cancelar", width="stretch", key=f"et_no_{t['id']}"):
        st.rerun()


# ---------------------------------------------------------------------------------------------------------------
# Lista
# ---------------------------------------------------------------------------------------------------------------
titulo("calendar", "Tareas de tus clases", nivel=3)
f1, f2 = st.columns([2, 3], vertical_alignment="bottom")
filtro_clase = f1.selectbox("Clase", [0, *etiquetas_clase], format_func=lambda i: "Todas las clases" if i == 0 else etiquetas_clase[i],
                            key="filtro_clase_tareas")
filtro_estado = f2.radio("Mostrar", ["Todas", "Programadas", "Vigentes", "Vencidas"], horizontal=True, key="filtro_estado_tareas")


def _coincide(t: dict) -> bool:
    if filtro_clase and t["clase_id"] != filtro_clase:
        return False
    return {"Todas": True, "Programadas": t["programada"], "Vencidas": t["vencida"] and not t["programada"],
            "Vigentes": not t["programada"] and not t["vencida"]}[filtro_estado]


mostradas = sorted((t for t in todas if _coincide(t)),
                   key=lambda t: (t["vencida"] and not t["programada"], t["fecha_limite"], t["id"]))
if not mostradas:
    st.caption("No hay tareas con ese filtro. Programa una arriba." if not todas else "No hay tareas con ese filtro.")
for t in mostradas:
    with st.container(border=True, key=f"tarea_m_{t['id']}"):
        titulo("clipboard", t["descripcion"], nivel=5)
        if t["programada"]:
            estado = ("Programada", "ambar", "clock")
        elif t["vencida"]:
            estado = ("Vencida", "rojo", "x")
        else:
            estado = ("Vigente", "verde", "check")
        etiquetas = [estado, (f"{tareas.texto_plazo(t['fecha_limite'], ahora, zona)} · {fecha_local(t['fecha_limite']):%d/%m/%Y %H:%M}",
                              "indigo", "calendar")]
        if t["programada"]:
            etiquetas.append((f"Se publica el {fecha_local(t['visible_desde']):%d/%m/%Y %H:%M}", "cielo", "clock"))
        insignias(*etiquetas)
        st.markdown(f"**{t['tema']}** · {t['clase']}")
        if t["instrucciones"]:
            st.caption(t["instrucciones"])
        if not t["programada"]:
            st.progress(t["hechas"] / t["alumnos"] if t["alumnos"] else 0.0,
                        text=f"{t['hechas']} de {t['alumnos']} alumnos la cumplieron")
        e1, e2, _ = st.columns([1.2, 1.2, 4])
        if e1.button("Editar", key=f"editar_{t['id']}", icon=":material/edit:", width="stretch"):
            editar_tarea(t)
        if e2.button("Borrar", key=f"borrar_t_{t['id']}", icon=":material/delete:", width="stretch"):
            listo(tareas.eliminar(user["id"], t["id"]))

st.caption("El avance de cada alumno y el Excel de cumplimiento están en «Clases», pestaña «Tareas».")
