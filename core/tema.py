import secrets
import time

import streamlit as st

from core import estilo

PARAM = "cambio_tema"
VIGENCIA = 60  # segundos

# Streamlit guarda la preferencia por ruta, se fija en todas las páginas de la app
RUTAS = ["/", "/chat", "/progreso", "/historial", "/cuenta", "/reticula", "/material", "/estadisticas", "/admin", "/login"]


@st.cache_resource
def _pendientes() -> dict:
    return {}


def _emitir(user: dict | None) -> str:
    pendientes, ahora = _pendientes(), time.time()
    for k in [k for k, (_, vence) in pendientes.items() if vence < ahora]:
        del pendientes[k]
    codigo = secrets.token_urlsafe(32)
    pendientes[codigo] = (user, ahora + VIGENCIA)
    return codigo


def restaurar_sesion() -> None:
    #Si la página se recargó por un cambio de tema, devuelve al usuario a su sesión
    codigo = st.query_params.get(PARAM)
    if not codigo:
        return
    del st.query_params[PARAM]
    item = _pendientes().pop(codigo, None)
    if item and item[1] >= time.time() and item[0] and "user" not in st.session_state:
        st.session_state["user"] = item[0]


# JavaScript que guarda la preferencia y recarga
_CAMBIAR = st.components.v2.component("cambio_de_tema", js="""
export default function ({ data }) {
  const valor = JSON.stringify(data.modo);
  for (const ruta of data.rutas) localStorage.setItem("stActiveTheme-" + ruta + "-v2", valor);
  window.location.href = window.location.pathname + "?" + data.param + "=" + encodeURIComponent(data.codigo);
}
""")


def _aplicar(destino: str, codigo: str) -> None:
    _CAMBIAR(data={"modo": destino, "rutas": RUTAS, "param": PARAM, "codigo": codigo}, key="cambio_de_tema")

def boton(en_barra_lateral: bool = True) -> None:
    # Botón Modo oscuro / Modo claro al presionarlo se guarda la preferencia y se recarga la página.
    oscuro = estilo.es_oscuro()
    contenedor = st.sidebar if en_barra_lateral else st
    etiqueta, icono = ("Modo claro", ":material/light_mode:") if oscuro else ("Modo oscuro", ":material/dark_mode:")
    if contenedor.button(etiqueta, icon=icono, width="stretch", key=f"btn_tema_{int(en_barra_lateral)}"):
        _aplicar("Light" if oscuro else "Dark", _emitir(st.session_state.get("user")))
