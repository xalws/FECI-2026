from datetime import datetime

import pandas as pd
import streamlit as st
from sqlalchemy import func, select

from core import perfil, respaldo
from core.auth import crear_usuario, require_login
from core.db import get_session
from core.estilo import datos, encabezado, titulo
from core.ui import NIVELES, selector_cascada
from models.schema import Asignacion, Carrera, Cuatrimestre, Materia, Universidad, Usuario

user = require_login(["admin"])

ROLES = {"admin": "Admin", "maestro": "Maestro", "alumno": "Alumno"}

# Los íconos, títulos y estilos vienen de core/estilo.py (compartidos por todas las pantallas)

# Encabezado
encabezado("Panel de administración", "Catálogo académico, cuentas de usuario y materias de cada maestro.",
           "shield", chips=[("user", f"Sesión de {user['nombre']}")])

# Resumen (métricas)
with get_session() as s:
    total_usuarios = s.scalar(select(func.count(Usuario.id))) or 0
    total_maestros = s.scalar(select(func.count(Usuario.id)).where(Usuario.rol == "maestro")) or 0
    total_alumnos = s.scalar(select(func.count(Usuario.id)).where(Usuario.rol == "alumno")) or 0
    total_asig = s.scalar(select(func.count(Asignacion.id))) or 0

datos([{"icono": "users", "etiqueta": "Usuarios", "valor": total_usuarios, "detalle": "cuentas registradas",
        "tono": "indigo"},
       {"icono": "user", "etiqueta": "Maestros", "valor": total_maestros, "detalle": "pueden subir material",
        "tono": "violeta"},
       {"icono": "cap", "etiqueta": "Alumnos", "valor": total_alumnos, "detalle": "estudian con el tutor",
        "tono": "cielo"},
       {"icono": "link", "etiqueta": "Asignaciones", "valor": total_asig, "detalle": "materias con maestro",
        "tono": "verde"}])

st.write("")
tab_cat, tab_usr, tab_asig = st.tabs([
    ":material/menu_book: Catálogo",
    ":material/group: Usuarios",
    ":material/link: Asignar maestros",
])

# Catálogo
with tab_cat:
    titulo("book", "Catálogo académico")
    st.caption("Crea universidades, carreras, cuatrimestres, materias, unidades y temas.")
    nombres_niveles = [n for n, _, _ in NIVELES]

    with st.container(border=True):
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

        col_form, col_lista = st.columns([3, 2])

        with col_form:
            with st.container(border=True):
                with st.form("form_catalogo", clear_on_submit=True, border=False):
                    nombre = st.text_input(
                        f"Nombre de la nueva {nivel}" if nivel in ("carrera", "materia", "unidad")
                        else f"Nombre del nuevo {nivel}"
                    )
                    if st.form_submit_button("Crear", type="primary", icon=":material/add:"):
                        nombre = nombre.strip()
                        if not nombre:
                            st.error("Escribe un nombre.")
                        elif nombre in existentes:
                            st.error("Ya existe uno con ese nombre.")
                        else:
                            with get_session() as s:
                                valores = {"nombre": nombre}
                                if fk:
                                    valores[fk] = padre_id
                                s.add(modelo(**valores))
                            st.toast(f"Creado: {nombre}", icon=":material/check_circle:")
                            st.rerun()

        with col_lista:
            with st.container(border=True):
                st.markdown(f"**Ya existen ({len(existentes)})**")
                if existentes:
                    for e in existentes:
                        st.markdown(f"- {e}")
                else:
                    st.caption("Todavía no hay registros aquí.")

# Usuarios
with tab_usr:
    titulo("user_plus", "Nuevo usuario")
    with st.container(border=True):
        with st.form("form_usuario", clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre")
            email = c2.text_input("Correo")
            c3, c4 = st.columns(2)
            password = c3.text_input("Contraseña inicial", type="password")
            rol = c4.selectbox("Rol", ["maestro", "alumno", "admin"], format_func=ROLES.get)
            if st.form_submit_button("Crear usuario", type="primary", icon=":material/person_add:"):
                ok, msg = crear_usuario(nombre, email, password, rol)
                (st.success if ok else st.error)(msg)

    titulo("users", "Lista de usuarios")
    with get_session() as s:
        usuarios = s.scalars(select(Usuario).order_by(Usuario.id)).all()
    filtro_u = st.text_input("Buscar usuario", placeholder="Nombre, correo o rol",
                             key="buscar_usuario", icon=":material/search:").strip().lower()
    if filtro_u:
        usuarios = [u for u in usuarios if filtro_u in f"{u.nombre} {u.email} {u.rol}".lower()]
    mapa = perfil.mapa_academico()
    filas_u = []
    for u in usuarios:
        uni, car, cua = mapa.get(u.cuatrimestre_id, ("", "", ""))
        filas_u.append({"id": u.id, "nombre": u.nombre, "correo": u.email,
                        "rol": ROLES.get(u.rol, u.rol), "activo": u.activo,
                        "universidad": uni, "carrera": car, "cuatrimestre/semestre": cua})
    st.caption(f"{len(filas_u)} usuario(s)")
    st.dataframe(
        pd.DataFrame(filas_u),
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", width="small"),
            "activo": st.column_config.CheckboxColumn("Activo", width="small"),
        },
    )

    # Editar datos académicos
    titulo("cap", "Datos académicos del alumno")
    aviso = st.session_state.pop("aviso_edit", None)
    if aviso:
        st.success(aviso)
    alumnos = {u.id: f"{u.nombre} ({u.email})" for u in usuarios if u.rol == "alumno"}
    if not alumnos:
        st.info("No hay alumnos que coincidan con la búsqueda.")
    else:
        with st.container(border=True):
            uid_al = st.selectbox("Alumno", list(alumnos), format_func=alumnos.get, key="edit_alumno")
            actual = mapa.get(perfil.cuatrimestre_de(uid_al))
            st.caption("Actual: " + " › ".join(actual) if actual
                       else "Actual: sin universidad/cuatrimestre asignado")
            st.write("Nuevo valor:")
            sel_e = selector_cascada(hasta="cuatrimestre", prefix="edit_al", buscar=False)
            if sel_e.get("cuatrimestre") and st.button("Guardar datos académicos", type="primary",
                                                        icon=":material/save:"):
                perfil.asignar_cuatrimestre(uid_al, sel_e["cuatrimestre"])
                st.session_state["aviso_edit"] = f"Datos de {alumnos[uid_al]} actualizados."
                st.rerun()

    # Activar / desactivar
    titulo("lock", "Activar / desactivar cuenta")
    otros = {u.id: f"{u.nombre} ({u.email})" for u in usuarios if u.id != user["id"]}
    if otros:
        with st.container(border=True):
            uid = st.selectbox("Usuario", list(otros), format_func=otros.get)
            if st.button("Cambiar estado (activo / inactivo)", icon=":material/sync_alt:"):
                with get_session() as s:
                    u = s.get(Usuario, uid)
                    u.activo = not u.activo
                st.rerun()

# Asignaciones
with tab_asig:
    titulo("link", "Asignar materia a un maestro")
    with get_session() as s:
        maestros = s.scalars(select(Usuario).where(Usuario.rol == "maestro", Usuario.activo.is_(True))).all()
    if not maestros:
        st.info("Primero crea al menos un usuario con rol maestro.")
    else:
        nombres_m = {m.id: f"{m.nombre} ({m.email})" for m in maestros}
        with st.container(border=True):
            maestro_id = st.selectbox("Maestro", list(nombres_m), format_func=nombres_m.get)
            st.caption("Materia que podrá administrar:")
            sel = selector_cascada(hasta="materia", prefix="adm_asig")
            materia_id = sel.get("materia")
            if materia_id and st.button("Asignar materia", type="primary", icon=":material/link:"):
                with get_session() as s:
                    ya = s.scalar(select(Asignacion.id).where(Asignacion.maestro_id == maestro_id,
                                                              Asignacion.materia_id == materia_id))
                    if ya:
                        st.warning("Ya estaba asignada.")
                    else:
                        s.add(Asignacion(maestro_id=maestro_id, materia_id=materia_id))
                        st.success("Asignada.")

    st.divider()
    titulo("users", "Asignaciones actuales")
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
                                 key="buscar_asig", icon=":material/search:").strip().lower()
        etiquetas = {k: v for k, v in etiquetas.items() if filtro_a in v.lower()}
        if not etiquetas:
            st.info("Ninguna asignación coincide.")
        else:
            st.dataframe(pd.DataFrame({"asignación": etiquetas.values()}), hide_index=True)
            with st.container(border=True):
                quitar = st.selectbox("Quitar asignación", list(etiquetas), format_func=etiquetas.get)
                if st.button("Quitar", icon=":material/delete:"):
                    with get_session() as s:
                        s.delete(s.get(Asignacion, quitar))
                    st.rerun()
    else:
        st.caption("Aún no hay asignaciones.")

# Respaldo de la base
st.write("")
titulo("shield", "Respaldo de la base")
with st.container(border=True):
    st.caption("Descarga una copia de todos los datos (usuarios, clases, avance, material…) en un archivo .zip. "
               "Incluye los códigos cifrados de las contraseñas: guárdalo en un lugar seguro y no lo compartas. "
               "También puedes automatizarlo con `python scripts/respaldo.py`.")
    sin_vectores = st.checkbox("Sin los vectores del material (archivo más ligero)", key="respaldo_sin_vectores",
                               help="Los vectores se recalculan al volver a subir los PDF.")
    if st.button("Preparar respaldo", icon=":material/backup:", key="respaldo_preparar"):
        with st.spinner("Copiando la base…"):
            contenido, manifiesto = respaldo.crear(incluir_vectores=not sin_vectores)
        st.session_state["respaldo_listo"] = (contenido, manifiesto)
    listo = st.session_state.get("respaldo_listo")
    if listo:
        contenido, manifiesto = listo
        st.success(f"Respaldo listo: {sum(manifiesto['filas'].values())} filas en {len(manifiesto['filas'])} tablas "
                   f"({len(contenido) / 1024:.0f} KB).", icon=":material/check_circle:")
        st.download_button("Descargar respaldo (.zip)", contenido, type="primary", icon=":material/download:",
                           file_name=f"respaldo_{datetime.now():%Y-%m-%d_%H%M}.zip", mime="application/zip",
                           key="respaldo_descargar")