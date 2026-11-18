import time
from datetime import date, datetime, timedelta, timezone, tzinfo

import streamlit as st
from sqlalchemy import select

from core.cache import memo, sin_transaccion
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
        with sin_transaccion(), get_session() as s:  # una sola instrucción en cada pantalla: 1 viaje a la base, no 3
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


@memo(ttl=30)
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


def dias_seguidos(dias: set[date], hoy: date) -> int:
    # Días consecutivos con actividad que terminan hoy, o ayer si hoy todavía no ha entrado.
    dia = hoy if hoy in dias else hoy - timedelta(days=1)
    racha = 0
    while dia in dias:
        racha += 1
        dia -= timedelta(days=1)
    return racha


def marcas_recientes(usuario_id: int, dias: int = 366) -> list[datetime]:
    # Marcas de actividad del último año (con zona UTC, también cuando SQLite las devuelve sin ella).
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    try:
        with get_session() as s:
            fechas = s.scalars(select(Actividad.fecha).where(Actividad.usuario_id == usuario_id,
                                                             Actividad.fecha >= desde)).all()
    except Exception:
        return []
    return [f if f.tzinfo else f.replace(tzinfo=timezone.utc) for f in fechas]


def dias_con_marcas(marcas: list[datetime], zona: tzinfo) -> set[date]:
    return {m.astimezone(zona).date() for m in marcas}


def racha_maxima(dias: set[date]) -> int:
    # La racha más larga de días seguidos que haya tenido.
    mejor = actual = 0
    anterior = None
    for d in sorted(dias):
        actual = actual + 1 if anterior is not None and d - anterior == timedelta(days=1) else 1
        mejor = max(mejor, actual)
        anterior = d
    return mejor


@memo(ttl=30)
def racha_dias(usuario_id: int, zona: tzinfo) -> int:
    # Racha de días seguidos usando la app, contados en la zona horaria del alumno.
    dias = dias_con_marcas(marcas_recientes(usuario_id), zona)
    return dias_seguidos(dias, datetime.now(zona).date())
