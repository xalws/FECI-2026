"""Meta diaria de estudio y logros del alumno.

Todo se calcula con lo que la app ya guarda (actividad, respuestas de quiz y ejercicios); lo único nuevo en la base
de datos es la meta diaria elegida (`usuarios.meta_diaria_min`). Los logros no se «guardan»: se evalúan cada vez
con reglas puras (`evaluar`), así que un cambio de reglas se aplica solo.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, tzinfo

from sqlalchemy import case, func, select

from core import actividad, niveles
from core.db import get_session
from models.schema import IntentoEjercicio, Quiz, RespuestaQuiz, Usuario

METAS_MIN = (10, 15, 20, 30, 45, 60)
META_DEFECTO = 20
SEMANAS_CALENDARIO = 5


def minutos_por_dia(marcas: list[datetime], zona: tzinfo) -> dict[date, float]:
    """Minutos de uso de cada día (hora local), con la misma regla de pausas que el tiempo total de estudio."""
    por_dia: dict[date, list] = defaultdict(list)
    for m in marcas:
        por_dia[m.astimezone(zona).date()].append(m)
    return {d: actividad.segundos_de_uso(ms) / 60 for d, ms in por_dia.items()}


def meta_de(usuario_id: int) -> int:
    with get_session() as s:
        meta = s.scalar(select(Usuario.meta_diaria_min).where(Usuario.id == usuario_id))
    return meta if meta in METAS_MIN else META_DEFECTO


def guardar_meta(usuario_id: int, minutos: int) -> None:
    if minutos not in METAS_MIN:
        raise ValueError("Elige una de las metas disponibles.")
    with get_session() as s:
        u = s.get(Usuario, usuario_id)
        if u is not None:
            u.meta_diaria_min = minutos


def dias_meta_cumplida(minutos: dict[date, float], meta: int) -> int:
    return sum(1 for m in minutos.values() if m >= meta)


def datos_alumno(usuario_id: int, zona: tzinfo, hoy: date | None = None) -> dict:
    """Todo lo necesario para pintar la meta, el calendario y los logros (una consulta por tabla)."""
    hoy = hoy or datetime.now(zona).date()
    marcas = actividad.marcas_recientes(usuario_id)
    minutos = minutos_por_dia(marcas, zona)
    dias = set(minutos) | actividad.dias_con_marcas(marcas, zona)
    meta = meta_de(usuario_id)
    with get_session() as s:
        total, aciertos = s.execute(
            select(func.count(RespuestaQuiz.id), func.coalesce(func.sum(case((RespuestaQuiz.es_correcta.is_(True), 1), else_=0)), 0))
            .where(RespuestaQuiz.alumno_id == usuario_id)).one()
        ejercicios, mejor = s.execute(
            select(func.count(IntentoEjercicio.id), func.coalesce(func.max(IntentoEjercicio.puntaje), 0))
            .where(IntentoEjercicio.alumno_id == usuario_id)).one()
        temas = set(s.scalars(select(Quiz.tema_id).join(RespuestaQuiz, RespuestaQuiz.quiz_id == Quiz.id)
                              .where(RespuestaQuiz.alumno_id == usuario_id)))
        temas |= set(s.scalars(select(IntentoEjercicio.tema_id).where(IntentoEjercicio.alumno_id == usuario_id)))
        resp, ejer = niveles._por_tema(s, usuario_id, list(temas)) if temas else ({}, {})
    mejor_nivel = max((niveles.calcular_estado(resp.get(t, []), ejer.get(t, []))["nivel"] for t in temas), default=0)
    return {"respuestas": int(total), "aciertos": int(aciertos), "ejercicios": int(ejercicios),
            "mejor_ejercicio": int(mejor), "mejor_nivel": mejor_nivel, "meta": meta, "hoy": hoy,
            "minutos": minutos, "minutos_hoy": minutos.get(hoy, 0.0),
            "racha": actividad.dias_seguidos(dias, hoy), "racha_maxima": actividad.racha_maxima(dias),
            "dias_meta": dias_meta_cumplida(minutos, meta)}


# (id, título, descripción, ícono, tono, clave del dato, meta numérica)
CATALOGO = [
    ("primeros_pasos", "Primeros pasos", "Responde tu primera pregunta de un examen", "play", "cielo", "respuestas", 1),
    ("diez_aciertos", "Buen ojo", "Acumula 10 respuestas correctas", "check", "verde", "aciertos", 10),
    ("cincuenta_aciertos", "Puntería", "Acumula 50 respuestas correctas", "target", "verde", "aciertos", 50),
    ("racha_3", "Constante", "Estudia 3 días seguidos", "flame", "ambar", "racha_maxima", 3),
    ("racha_7", "Imparable", "Estudia 7 días seguidos", "flame", "ambar", "racha_maxima", 7),
    ("racha_14", "Hábito de acero", "Estudia 14 días seguidos", "flame", "rojo", "racha_maxima", 14),
    ("ejercicios_5", "Practicante", "Resuelve 5 ejercicios prácticos", "bulb", "violeta", "ejercicios", 5),
    ("ejercicio_9", "Matrícula de honor", "Saca 9 o más en un ejercicio", "star", "ambar", "mejor_ejercicio", 9),
    ("meta_5", "Cumplidor", "Cumple tu meta diaria durante 5 días", "clock", "indigo", "dias_meta", 5),
    ("nivel_avanzado", "Cada vez más alto", "Llega a nivel Avanzado en un tema", "trending", "indigo", "mejor_nivel", 3),
    ("experto", "Experto", "Llega a nivel Experto en un tema", "award", "rosa", "mejor_nivel", 4),
]


def evaluar(datos: dict) -> list[dict]:
    """Cada logro con su avance: {id, titulo, descripcion, icono, tono, actual, meta, logrado}."""
    salida = []
    for id_, titulo, descripcion, icono, tono, clave, meta in CATALOGO:
        actual = min(int(datos.get(clave, 0)), meta)
        salida.append({"id": id_, "titulo": titulo, "descripcion": descripcion, "icono": icono, "tono": tono,
                       "actual": actual, "meta": meta, "logrado": actual >= meta})
    return salida


def ids_logrados(usuario_id: int, zona: tzinfo) -> set[str]:
    return {l["id"] for l in evaluar(datos_alumno(usuario_id, zona)) if l["logrado"]}


def revisar_nuevos(usuario_id: int, zona: tzinfo, datos: dict | None = None) -> list[dict]:
    """Avisa con un mensaje emergente los logros conseguidos desde la última revisión de esta sesión.

    La primera revisión de cada sesión solo toma nota (sin avisar), para no repetir logros viejos.
    """
    import streamlit as st

    ss = st.session_state
    por_id = {l["id"]: l for l in evaluar(datos or datos_alumno(usuario_id, zona))}
    logrados = {i for i, l in por_id.items() if l["logrado"]}
    vistos = ss.get("logros_vistos")
    ss["logros_vistos"] = logrados | (vistos or set())
    if vistos is None:
        return []
    nuevos = [por_id[i] for i in sorted(logrados - vistos)]
    for logro in nuevos:
        st.toast(f"¡Logro desbloqueado: {logro['titulo']}!", icon=":material/emoji_events:")
    return nuevos


def calendario(minutos: dict[date, float], hoy: date, semanas: int = SEMANAS_CALENDARIO) -> list[list[dict]]:
    """Cuadrícula de semanas (lunes a domingo) que termina en la semana de `hoy`.

    Cada celda: {"fecha", "minutos", "futuro"}; las semanas van de la más antigua a la más reciente.
    """
    lunes_actual = hoy - timedelta(days=hoy.weekday())
    inicio = lunes_actual - timedelta(weeks=semanas - 1)
    filas = []
    for w in range(semanas):
        fila = []
        for d in range(7):
            dia = inicio + timedelta(weeks=w, days=d)
            fila.append({"fecha": dia, "minutos": minutos.get(dia, 0.0), "futuro": dia > hoy})
        filas.append(fila)
    return filas
