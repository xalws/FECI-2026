"""El maestro sube la retícula (programa de asignatura) y la app crea la materia con sus unidades y temas."""
import streamlit as st
from sqlalchemy import select

from core import reticula
from core.auth import require_login
from core.db import get_session
from models.schema import Carrera, Cuatrimestre, Universidad

user = require_login(["maestro", "admin"])
ss = st.session_state

st.title("Retícula de la materia")
st.write("Sube el **programa de la asignatura** (PDF). La app lee sus unidades y temas y crea la materia. "
         "Después, el material de clase se reparte entre esos temas.")

archivo = st.file_uploader("PDF de la retícula", type="pdf", key="pdf_reticula")
if archivo and st.button("Leer retícula", type="primary"):
    try:
        with st.spinner("Leyendo la retícula…"):
            ss.reticula_pendiente = {"datos": reticula.extraer(archivo), "archivo": archivo.name}
    except Exception as e:
        ss.pop("reticula_pendiente", None)
        st.error(str(e))

pend = ss.get("reticula_pendiente")
if not pend:
    st.stop()

datos = pend["datos"]
st.divider()
st.subheader(datos["materia"])
n_temas = sum(len(u["temas"]) for u in datos["unidades"])
st.caption(f"{len(datos['unidades'])} unidades y {n_temas} temas encontrados en «{pend['archivo']}».")
for i, u in enumerate(datos["unidades"], 1):
    with st.expander(f"Unidad {i}: {u['nombre']}", expanded=i == 1):
        for t in u["temas"]:
            st.markdown(f"**{t['nombre']}**")
            if t["objetivos"]:
                st.caption(t["objetivos"])

NUEVO = "➕ Escribir uno nuevo…"


def elegir_o_crear(etiqueta: str, existentes: list[str], sugerido: str, key: str) -> str:
    # Lista desplegable con lo que ya existe; si no está, se escribe el nombre.
    opciones = existentes + [NUEVO]
    coincide = [i for i, n in enumerate(existentes) if reticula._normalizar(n) == reticula._normalizar(sugerido)]
    indice = coincide[0] if coincide else (len(existentes) if sugerido or not existentes else 0)
    elegido = st.selectbox(etiqueta, opciones, index=indice, key=f"{key}_sel")
    if elegido == NUEVO:
        return st.text_input(f"{etiqueta} (nuevo)", value=sugerido, key=f"{key}_nuevo").strip()
    return elegido


def _buscar(s, modelo, nombre: str, **filtros):
    for fila in s.scalars(select(modelo).filter_by(**filtros)):
        if reticula._normalizar(fila.nombre) == reticula._normalizar(nombre):
            return fila
    return None


st.subheader("¿Dónde guardarla?")
with get_session() as s:
    unis = [u.nombre for u in s.scalars(select(Universidad).order_by(Universidad.nombre))]
uni = elegir_o_crear("Universidad", unis, "", "ret_uni")
carreras, cuatrimestres = [], []
if uni:
    with get_session() as s:
        u_fila = _buscar(s, Universidad, uni)
        if u_fila:
            carreras = [c.nombre for c in s.scalars(select(Carrera).where(Carrera.universidad_id == u_fila.id))]
car = elegir_o_crear("Carrera", carreras, datos["carrera"], "ret_car")
if uni and car:
    with get_session() as s:
        u_fila = _buscar(s, Universidad, uni)
        c_fila = _buscar(s, Carrera, car, universidad_id=u_fila.id) if u_fila else None
        if c_fila:
            cuatrimestres = [q.nombre for q in s.scalars(select(Cuatrimestre)
                                                        .where(Cuatrimestre.carrera_id == c_fila.id))]
cua = elegir_o_crear("Cuatrimestre / semestre", cuatrimestres, datos["cuatrimestre"], "ret_cua")

if st.button("Crear materia y temas", type="primary"):
    if not (uni and car and cua):
        st.error("Completa universidad, carrera y cuatrimestre.")
    else:
        resumen = reticula.crear_desde_reticula(datos, uni, car, cua, user["id"])
        ss.pop("reticula_pendiente", None)
        st.success(f"Listo: {resumen['unidades_nuevas']} unidades y {resumen['temas_nuevos']} temas nuevos "
                   f"({resumen['temas_actualizados']} temas actualizados). Ahora ve a «Material de la IA» y sube "
                   "los PDFs de la materia: se repartirán entre estos temas.")
