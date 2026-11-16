import streamlit as st
from sqlalchemy import select

from core import actividad, cuenta, estilo, seguridad, sesion, tema
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


def intentar_login(email: str, password: str) -> tuple[dict | None, str]:
    """Inicia sesión con límite de intentos: devuelve (usuario, "") o (None, motivo para mostrar).

    Tras `seguridad.MAX_FALLOS` fallos el correo se bloquea `seguridad.VENTANA_MIN` minutos; mientras tanto ni siquiera
    se revisa la contraseña (acertarla tampoco sirve), para que adivinar no avance.
    """
    espera = seguridad.segundos_de_bloqueo(email)
    if espera:
        return None, f"Demasiados intentos fallidos. Vuelve a intentarlo en {seguridad.texto_de_espera(espera)}."
    u = login(email, password)
    if u:
        seguridad.limpiar(email)
        return u, ""
    seguridad.registrar_fallo(email)
    espera = seguridad.segundos_de_bloqueo(email)
    if espera:
        return None, f"Demasiados intentos fallidos. Vuelve a intentarlo en {seguridad.texto_de_espera(espera)}."
    quedan = seguridad.intentos_restantes(email)
    aviso = f" Te {'queda' if quedan == 1 else 'quedan'} {quedan} {'intento' if quedan == 1 else 'intentos'}." if quedan <= 2 else ""
    return None, "Correo o contraseña incorrectos." + aviso


def crear_usuario(nombre: str, email: str, password: str, rol: str,
                  cuatrimestre_id: int | None = None) -> tuple[bool, str]:
    nombre, email = nombre.strip(), email.strip().lower()
    if not nombre or "@" not in email:
        return False, "Escribe un nombre y un correo válido."
    error = cuenta.validar_password(password, email)
    if error:
        return False, error
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
    sesion.revocar(st.session_state.get("_token_sesion"))  # el código recordado deja de servir
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["_inicio_hecho"] = True  # no volver a mostrar la pantalla de carga de arranque
    sesion.cerrar()  # borra la cookie del navegador


def barra_lateral(user: dict) -> None:
    # Tarjeta del usuario, modo claro/oscuro y cerrar sesión: el CSS (core/estilo.py) manda este bloque al
    # final del menú lateral, debajo del selector de tema de cada pantalla
    with st.sidebar.container(key="bloque_usuario"):
        # La tarjeta del usuario es el acceso a «Mi cuenta»: un enlace invisible la cubre (el CSS oculta la página del menú)
        with st.container(key="tarjeta_usuario_link"):
            estilo.tarjeta_usuario(user)
            st.page_link("vistas/cuenta.py", label="Mi cuenta", icon=":material/manage_accounts:")
        tema.boton()
        if st.button("Cerrar sesión", icon=":material/logout:", width="stretch", key="btn_cerrar_sesion"):
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
