"""Caché de lecturas de la base, para que cambiar de pantalla no repita decenas de consultas.

Con una base remota cada consulta cuesta ~70 ms (y ~140 ms si abre una transacción nueva), así que una pantalla con 20
consultas tarda más de 2 segundos. Las funciones marcadas con `@memo` guardan su resultado y lo reutilizan mientras
no cambie nada.

Cuándo se vacía:
- **Al escribir:** cualquier INSERT, UPDATE o DELETE confirmado en este proceso sube un contador de versión y todo lo
  guardado deja de servir (el contador es parte de la clave). Así, después de responder una pregunta, subir un
  archivo o unirse a una clase, la pantalla siguiente ya ve el dato nuevo. Las marcas de actividad y las sesiones
  se escriben en cada recarga y no cuentan, o la caché nunca serviría.
- **Por tiempo (`TTL`):** si otra persona escribe desde otro proceso (otra computadora con la misma base) no hay forma
  de enterarse, así que lo guardado vence a los 60 s.
Fuera de Streamlit (pruebas, scripts) no se guarda nada: las funciones se ejecutan siempre.
"""
import functools
import os
from contextvars import ContextVar
from datetime import tzinfo

import streamlit as st

TTL = 60
# Mientras una lectura guardada se ejecuta, `get_session` usa una conexión sin transacción (AUTOCOMMIT): una consulta
# cuesta 1 viaje a la base en lugar de 3 (abrir transacción, consultar, cerrar). Por eso `@memo` es solo para lecturas.
modo_lectura: ContextVar[bool] = ContextVar("modo_lectura", default=False)
# Escrituras que ocurren en cada recarga de pantalla y no cambian lo que se muestra
_IGNORADAS = ("INSERT INTO actividad", "INSERT INTO sesiones", "UPDATE sesiones", "DELETE FROM sesiones")
_version = 0


def version() -> int:
    return _version


def invalidar() -> None:
    """Hace que todo lo guardado deje de servir."""
    global _version
    _version += 1


def es_escritura(sql: str) -> bool:
    """True si la sentencia cambia datos que se muestran (no cuentan las de `_IGNORADAS`)."""
    s = sql.lstrip()
    return s[:6].upper() in ("INSERT", "UPDATE", "DELETE") and not s.startswith(_IGNORADAS)


def _clave(valor):
    if isinstance(valor, tzinfo):
        return getattr(valor, "key", None) or str(valor)
    if isinstance(valor, (list, tuple, set)):
        return tuple(_clave(v) for v in valor)
    if isinstance(valor, dict):
        return tuple(sorted((str(k), _clave(v)) for k, v in valor.items()))
    return valor if isinstance(valor, (int, float, str, bool, type(None))) else repr(valor)


def _en_streamlit() -> bool:
    if os.environ.get("PRACTIC_SIN_CACHE"):  # interruptor para comparar o descartar la caché si algo se ve raro
        return False
    try:
        return st.runtime.exists()
    except Exception:
        return False


def memo(funcion=None, *, ttl: int = TTL):
    """Guarda el resultado de una lectura de la base (ver el texto del módulo). Úsalo solo con funciones que no escriben."""
    def decorar(f):
        nombre = f"{f.__module__}.{f.__qualname__}"
        guardado = None  # se crea la primera vez que se usa dentro de Streamlit (fuera de él avisaría en cada importación)

        def leer(*args, **kwargs):
            marca = modo_lectura.set(True)
            try:
                return f(*args, **kwargs)
            finally:
                modo_lectura.reset(marca)

        @functools.wraps(f)
        def envoltura(*args, **kwargs):
            nonlocal guardado
            if not _en_streamlit():
                return leer(*args, **kwargs)
            if guardado is None:
                @st.cache_data(ttl=ttl, show_spinner=False, max_entries=1000)
                def guardado(nombre_fn, version_datos, clave_args, _args, _kwargs):
                    # Streamlit solo toma para la clave los parámetros que NO empiezan con «_»: los tres primeros
                    return leer(*_args, **_kwargs)
            clave = (_clave(args), _clave(kwargs))
            return guardado(nombre, _version, clave, args, kwargs)  # (nombre, versión y clave cuentan en la clave)

        envoltura.sin_cache = f
        return envoltura

    return decorar(funcion) if funcion is not None else decorar
