import streamlit as st
from sqlalchemy import select

from core import actividad
from core.db import get_session, init_db
from core.passwords import hash_password, verificar_password
from models.schema import Cuatrimestre, Usuario


@st.cache_resource
def iniciar_db() -> bool:
    # Crea tablas y admin inicial.
    init_db()
    return True


def login(email: str, password: str) -> dict | None:
    with get_session() as s:
        u = s.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
        if u and u.activo and verificar_password(password, u.password_hash):
            return {"id": u.id, "nombre": u.nombre, "email": u.email, "rol": u.rol}
    return None


def crear_usuario(nombre: str, email: str, password: str, rol: str,
                  cuatrimestre_id: int | None = None) -> tuple[bool, str]:
    nombre, email = nombre.strip(), email.strip().lower()
    if not nombre or "@" not in email:
        return False, "Escribe un nombre y un correo válido."
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."
    if rol not in ("alumno", "maestro", "admin"):
        return False, "Rol inválido."
    with get_session() as s:
        if s.scalar(select(Usuario.id).where(Usuario.email == email)):
            return False, "Ya existe un usuario con ese correo."
        if cuatrimestre_id is not None and s.get(Cuatrimestre, cuatrimestre_id) is None:
            return False, "El cuatrimestre elegido no existe."
        s.add(Usuario(nombre=nombre, email=email, password_hash=hash_password(password), rol=rol,
                      cuatrimestre_id=cuatrimestre_id if rol == "alumno" else None))
    return True, "Usuario creado."


def cerrar_sesion() -> None:
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def barra_lateral(user: dict) -> None:
    st.sidebar.markdown(f" **{user['nombre']}**  \nRol: `{user['rol']}`")
    if st.sidebar.button("Cerrar sesión"):
        cerrar_sesion()
        st.rerun()


def require_login(roles: list[str] | None = None) -> dict:
    iniciar_db()
    user = st.session_state.get("user")
    if not user:
        st.warning("Inicia sesión para continuar.")
        st.stop()
    if roles and user["rol"] not in roles:
        st.error("No tienes permiso para ver esta página.")
        st.stop()
    actividad.registrar(user["id"])
    barra_lateral(user)
    return user
