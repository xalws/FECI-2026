import pandas as pd
import streamlit as st
from sqlalchemy import select

from core.auth import crear_usuario, require_login
from core.db import get_session
from core.ui import NIVELES, selector_cascada
from models.schema import Asignacion, Carrera, Cuatrimestre, Materia, Universidad, Usuario

user = require_login(["admin"])

st.title("Administración")
tab_cat, tab_usr, tab_asig = st.tabs(["Catálogo", "Usuarios", "Asignar maestros"])

# ---------------------------------------------------------------- Catálogo
with tab_cat:
    st.write("Crea universidades, carreras, cuatrimestres, materias, unidades y temas.")
    nombres_niveles = [n for n, _, _ in NIVELES]
    nivel = st.selectbox("¿Qué quieres crear?", nombres_niveles, format_func=str.capitalize)
    idx = nombres_niveles.index(nivel)
    _, modelo, fk = NIVELES[idx]

    padre_id = None
    if idx > 0:
        st.caption("Elige dónde va a quedar:")
        padre_nivel = nombres_niveles[idx - 1]
        sel = selector_cascada(hasta=padre_nivel, prefix="adm_cat")
        padre_id = sel.get(padre_nivel)

    if idx == 0 or padre_id is not None:
        with get_session() as s:
            q = select(modelo.nombre).order_by(modelo.nombre)
            if fk:
                q = q.where(getattr(modelo, fk) == padre_id)
            existentes = list(s.scalars(q))
        if existentes:
            st.caption("Ya existen: " + ", ".join(existentes))
        with st.form("form_catalogo", clear_on_submit=True):
            nombre = st.text_input(f"Nombre de la nueva {nivel}" if nivel in ("carrera", "materia", "unidad")
                                   else f"Nombre de {nivel}")
            if st.form_submit_button("Crear"):
                nombre = nombre.strip()
                if not nombre:
                    st.error("Escribe un nombre.")
                elif nombre in existentes:
                    st.error("Ya existe uno con ese nombre.")
                else:
                    with get_session() as s:
                        datos = {"nombre": nombre}
                        if fk:
                            datos[fk] = padre_id
                        s.add(modelo(**datos))
                    st.success(f"Creado: {nombre}")
                    st.rerun()

# ---------------------------------------------------------------- Usuarios
with tab_usr:
    with st.form("form_usuario", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre")
        email = c2.text_input("Correo")
        c3, c4 = st.columns(2)
        password = c3.text_input("Contraseña inicial", type="password")
        rol = c4.selectbox("Rol", ["maestro", "alumno", "admin"])
        if st.form_submit_button("Crear usuario"):
            ok, msg = crear_usuario(nombre, email, password, rol)
            (st.success if ok else st.error)(msg)

    with get_session() as s:
        usuarios = s.scalars(select(Usuario).order_by(Usuario.id)).all()
    filtro_u = st.text_input("Buscar usuario", placeholder="Nombre, correo o rol",
                             key="buscar_usuario").strip().lower()
    if filtro_u:
        usuarios = [u for u in usuarios if filtro_u in f"{u.nombre} {u.email} {u.rol}".lower()]
    st.dataframe(pd.DataFrame([{"id": u.id, "nombre": u.nombre, "correo": u.email, "rol": u.rol,
                                "activo": u.activo} for u in usuarios]),
                 hide_index=True)

    st.caption("Activar / desactivar cuenta")
    otros = {u.id: f"{u.nombre} ({u.email})" for u in usuarios if u.id != user["id"]}
    if otros:
        uid = st.selectbox("Usuario", list(otros), format_func=otros.get)
        if st.button("Cambiar estado (activo ⇄ inactivo)"):
            with get_session() as s:
                u = s.get(Usuario, uid)
                u.activo = not u.activo
            st.rerun()

# ---------------------------------------------------------------- Asignaciones
with tab_asig:
    with get_session() as s:
        maestros = s.scalars(select(Usuario).where(Usuario.rol == "maestro", Usuario.activo.is_(True))).all()
    if not maestros:
        st.info("Primero crea al menos un usuario con rol maestro.")
    else:
        nombres_m = {m.id: f"{m.nombre} ({m.email})" for m in maestros}
        maestro_id = st.selectbox("Maestro", list(nombres_m), format_func=nombres_m.get)
        st.caption("Materia que podrá administrar:")
        sel = selector_cascada(hasta="materia", prefix="adm_asig")
        materia_id = sel.get("materia")
        if materia_id and st.button("Asignar materia"):
            with get_session() as s:
                ya = s.scalar(select(Asignacion.id).where(Asignacion.maestro_id == maestro_id,
                                                          Asignacion.materia_id == materia_id))
                if ya:
                    st.warning("Ya estaba asignada.")
                else:
                    s.add(Asignacion(maestro_id=maestro_id, materia_id=materia_id))
                    st.success("Asignada.")

    st.divider()
    st.subheader("Asignaciones actuales")
    with get_session() as s:
        filas = s.execute(
            select(Asignacion.id, Usuario.nombre, Materia.nombre, Cuatrimestre.nombre, Carrera.nombre,
                   Universidad.nombre)
            .join(Usuario, Usuario.id == Asignacion.maestro_id)
            .join(Materia, Materia.id == Asignacion.materia_id)
            .join(Cuatrimestre, Cuatrimestre.id == Materia.cuatrimestre_id)
            .join(Carrera, Carrera.id == Cuatrimestre.carrera_id)
            .join(Universidad, Universidad.id == Carrera.universidad_id)
        ).all()
    if filas:
        etiquetas = {f[0]: f"{f[1]} → {f[2]} ({f[3]}, {f[4]}, {f[5]})" for f in filas}
        filtro_a = st.text_input("Buscar asignación", placeholder="Maestro, materia, carrera…",
                                 key="buscar_asig").strip().lower()
        etiquetas = {k: v for k, v in etiquetas.items() if filtro_a in v.lower()}
        if not etiquetas:
            st.caption("Ninguna asignación coincide.")
        else:
            st.dataframe(pd.DataFrame({"asignación": etiquetas.values()}), hide_index=True)
            quitar = st.selectbox("Quitar asignación", list(etiquetas), format_func=etiquetas.get)
            if st.button("Quitar"):
                with get_session() as s:
                    s.delete(s.get(Asignacion, quitar))
                st.rerun()
    else:
        st.caption("Aún no hay asignaciones.")
