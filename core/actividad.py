import time

import streamlit as st
from sqlalchemy import select

from core.db import get_session
from models.schema import Actividad

SEGUNDOS_ENTRE_REGISTROS = 30   # no se guarda un registro por cada clic
PAUSA_MAX = 5 * 60              # una pausa mayor a esto no cuenta como tiempo de uso


def registrar(usuario_id: int) -> None:
    # Guarda una marca de actividad como máximo cada 30 s por sesión.
    ahora = time.time()
    if ahora - st.session_state.get("_ult_actividad", 0) < SEGUNDOS_ENTRE_REGISTROS:
        return
    st.session_state["_ult_actividad"] = ahora
    try:
        with get_session() as s:
            s.add(Actividad(usuario_id=usuario_id))
    except Exception:
        pass  # el registro de tiempo nunca debe romper la app


def segundos_de_uso(marcas: list) -> float:
    # Suma el tiempo entre marcas consecutivas, ignorando las pausas largas.
    marcas = sorted(marcas)
    total = 0.0
    for a, b in zip(marcas, marcas[1:]):
        dif = (b - a).total_seconds()
        if dif <= PAUSA_MAX:
            total += dif
    return total


def tiempo_por_alumno(alumno_ids: list[int]) -> dict[int, float]:
    # Segundos de uso de cada alumno (id -> segundos).
    if not alumno_ids:
        return {}
    with get_session() as s:
        filas = s.execute(select(Actividad.usuario_id, Actividad.fecha)
                          .where(Actividad.usuario_id.in_(alumno_ids))).all()
    por_alumno: dict[int, list] = {i: [] for i in alumno_ids}
    for uid, fecha in filas:
        por_alumno[uid].append(fecha)
    return {uid: segundos_de_uso(m) for uid, m in por_alumno.items()}
