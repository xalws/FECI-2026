"""Precarga en segundo plano de las librerías pesadas.

La primera persona que entra después de arrancar el servidor esperaba a que se importaran pandas, numpy, la búsqueda en
el material y los módulos de cada pantalla (en una computadora lenta o con el proyecto en OneDrive, más de 8 segundos).
Ahora se importan en un hilo aparte desde que se abre la pantalla de inicio de sesión, mientras se escribe la
contraseña, así que la primera pantalla de cada cuenta ya no carga todo desde cero.
"""
import importlib
import logging
import threading

import streamlit as st

MODULOS = (
    "pandas", "openpyxl",
    # maestro y administrador
    "core.clases", "core.tareas", "core.stats", "core.boletin", "core.perfil_ui", "core.competencia", "core.reticula",
    "core.respaldo",
    # alumno
    "core.niveles", "core.logros", "core.progreso", "core.repaso", "core.retos", "core.chat", "core.tutoria",
    "core.examen", "core.llm", "core.material", "core.rag",
)


def _importar() -> None:
    for nombre in MODULOS:
        try:
            importlib.import_module(nombre)
        except Exception as e:  # una precarga fallida no debe afectar a la app: la pantalla lo importará igual
            logging.getLogger(__name__).debug("precarga de %s: %s", nombre, e)


@st.cache_resource(show_spinner=False)
def iniciar() -> threading.Thread:
    """Arranca la precarga una sola vez por servidor."""
    hilo = threading.Thread(target=_importar, name="precarga", daemon=True)
    hilo.start()
    return hilo
