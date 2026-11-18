"""Sesión que sobrevive al recargar la página («Recordarme»).

Streamlit guarda la sesión en la memoria del servidor: al recargar el navegador se abre una sesión nueva y el
usuario tendría que escribir su contraseña otra vez. Para evitarlo, al iniciar sesión se crea un código largo y
aleatorio que se guarda en el navegador (cookie) y, en la base de datos, solo su huella (hash SHA-256), con fecha de
vencimiento. Al abrir la página, si la cookie trae un código vigente de una cuenta activa, se restaura la sesión.

- El código nunca se guarda tal cual en la base de datos: quien la lea no puede usarlo para entrar.
- Cerrar sesión, cambiar la contraseña (las otras sesiones) o desactivar la cuenta lo invalidan.
- La cookie la escribe JavaScript, así que no puede ser «HttpOnly»; por eso vence a los 14 días y se limita a
  SameSite=Lax. No conviene usar «Recordarme» en equipos compartidos (el inicio de sesión lo advierte).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import streamlit as st
from sqlalchemy import delete, or_, select

from core import cache
from core.db import get_session
from models.schema import Sesion, Usuario

COOKIE = "tu_sesion"
DURACION_DIAS = 14
MAX_SESIONES_POR_USUARIO = 10  # se borran las más viejas para que la tabla no crezca sin control


def _huella(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)  # SQLite la devuelve sin zona


def crear(usuario_id: int, dias: int = DURACION_DIAS) -> str:
    """Crea una sesión recordada y devuelve su código (es la única vez que se conoce completo)."""
    token = secrets.token_urlsafe(32)
    ahora = _ahora()
    # Dos instrucciones sin transacción (2 viajes a la base en lugar de 6): con la red lenta, iniciar sesión tardaba
    viejas = (select(Sesion.id).where(Sesion.usuario_id == usuario_id)
              .order_by(Sesion.creada.desc()).offset(MAX_SESIONES_POR_USUARIO - 1))
    with cache.sin_transaccion(), get_session() as s:
        # las vencidas de todos y, de este usuario, las que pasan del máximo (deja lugar para la nueva)
        s.execute(delete(Sesion).where(or_(Sesion.expira < ahora, Sesion.id.in_(viejas))))
        s.add(Sesion(usuario_id=usuario_id, token_hash=_huella(token), creada=ahora, expira=ahora + timedelta(days=dias)))
    return token


def validar(token: str | None) -> dict | None:
    """Datos del usuario si el código es vigente y su cuenta sigue activa; si no, None."""
    if not token or len(token) > 200:
        return None
    # Una sola consulta sin transacción: se hace en cada recarga de la página
    with cache.sin_transaccion(), get_session() as s:
        fila = s.execute(select(Sesion.expira, Usuario.id, Usuario.nombre, Usuario.email, Usuario.rol, Usuario.activo)
                         .join(Usuario, Usuario.id == Sesion.usuario_id)
                         .where(Sesion.token_hash == _huella(token))).first()
    if fila is None or _utc(fila.expira) <= _ahora() or not fila.activo:
        return None
    return {"id": fila.id, "nombre": fila.nombre, "email": fila.email, "rol": fila.rol}


def revocar(token: str | None) -> None:
    if token:
        with get_session() as s:
            s.execute(delete(Sesion).where(Sesion.token_hash == _huella(token)))


def revocar_todas(usuario_id: int, conservar: str | None = None) -> None:
    """Cierra todas las sesiones recordadas de un usuario (menos la del código `conservar`, si se da)."""
    with get_session() as s:
        q = delete(Sesion).where(Sesion.usuario_id == usuario_id)
        if conservar:
            q = q.where(Sesion.token_hash != _huella(conservar))
        s.execute(q)


# ---------------------------------------------------------------------------------------------------------------
# Parte de Streamlit: leer la cookie al abrir la página y escribirla o borrarla desde el navegador
# ---------------------------------------------------------------------------------------------------------------
# Se ejecuta en la propia página (no en un iframe, que no puede tocar las cookies de la app)
_COOKIE_JS = st.components.v2.component("cookie_de_sesion", js="""
export default function ({ data }) {
  const seguro = window.location.protocol === "https:" ? "; Secure" : "";
  const valor = data.accion === "poner" ? encodeURIComponent(data.valor) : "";
  const vida = data.accion === "poner" ? data.segundos : 0;
  document.cookie = data.nombre + "=" + valor + "; path=/; max-age=" + vida + "; SameSite=Lax" + seguro;
}
""")


def recordar(usuario_id: int) -> None:
    """Después de iniciar sesión: crea el código y deja pendiente escribirlo en el navegador."""
    token = crear(usuario_id)
    st.session_state["_token_sesion"] = token
    st.session_state["_cookie_pendiente"] = ("poner", token)
    st.session_state.pop("_sesion_cerrada", None)


def cerrar() -> None:
    """Al cerrar sesión: invalida el código en el servidor y deja pendiente borrar la cookie del navegador.

    Se llama DESPUÉS de vaciar el estado de la sesión (ver core/auth.py), por eso recibe el código ya leído.
    """
    st.session_state["_cookie_pendiente"] = ("borrar", "")
    st.session_state["_sesion_cerrada"] = True  # la cookie de esta conexión sigue «viva» hasta que el navegador la borre


def restaurar() -> None:
    """Primera línea de app.py: si no hay sesión pero la cookie trae un código vigente, la restaura."""
    ss = st.session_state
    if "user" in ss or ss.get("_sesion_cerrada"):
        return
    try:
        token = st.context.cookies.get(COOKIE)
    except Exception:
        return
    usuario = validar(token)
    if usuario:
        ss["user"] = usuario
        ss["_token_sesion"] = token
        ss["_cargando"] = True  # al recargar con la sesión recordada también puede tardar: se muestra la pantalla de carga
    elif token:  # vencida, revocada o de una cuenta dada de baja: se borra para no volver a probarla
        ss["_cookie_pendiente"] = ("borrar", "")


def aplicar_cookie_pendiente() -> None:
    """Escribe o borra la cookie en el navegador si quedó pendiente (se llama en cada ejecución de app.py)."""
    pendiente = st.session_state.pop("_cookie_pendiente", None)
    if pendiente:
        accion, valor = pendiente
        _COOKIE_JS(data={"accion": accion, "valor": valor, "nombre": COOKIE,
                         "segundos": DURACION_DIAS * 86400}, key=f"cookie_{accion}")
