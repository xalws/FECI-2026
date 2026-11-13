# Estadísticas para el maestro 
import pandas as pd
from sqlalchemy import text

from core.db import engine

SQL_MENSAJES = """
SELECT m.id AS mensaje_id, m.rol, m.fecha, c.id AS conversacion_id,
       c.alumno_id, u.nombre AS alumno, t.id AS tema_id, t.nombre AS tema,
       ma.id AS materia_id, ma.nombre AS materia
FROM mensajes m
JOIN conversaciones c ON c.id = m.conversacion_id
JOIN usuarios u ON u.id = c.alumno_id
JOIN temas t ON t.id = c.tema_id
JOIN unidades un ON un.id = t.unidad_id
JOIN materias ma ON ma.id = un.materia_id
"""

SQL_RESPUESTAS = """
SELECT r.id, r.es_correcta, r.fecha, r.alumno_id, u.nombre AS alumno,
       q.id AS quiz_id, q.pregunta, t.id AS tema_id, t.nombre AS tema,
       ma.id AS materia_id, ma.nombre AS materia
FROM respuestas_quiz r
JOIN quizzes q ON q.id = r.quiz_id
JOIN usuarios u ON u.id = r.alumno_id
JOIN temas t ON t.id = q.tema_id
JOIN unidades un ON un.id = t.unidad_id
JOIN materias ma ON ma.id = un.materia_id
"""


SQL_SIN_RESPUESTA = """
SELECT p.pregunta, p.fecha, u.nombre AS alumno, t.nombre AS tema,
       ma.id AS materia_id, ma.nombre AS materia
FROM preguntas_sin_respuesta p
JOIN usuarios u ON u.id = p.alumno_id
JOIN temas t ON t.id = p.tema_id
JOIN unidades un ON un.id = t.unidad_id
JOIN materias ma ON ma.id = un.materia_id
ORDER BY p.id DESC
"""


def preguntas_sin_respuesta(materias_ids: list[int] | None = None) -> pd.DataFrame:
    # Preguntas que el tutor no pudo contestar: señal de material que falta subir.
    with engine.connect() as conn:
        df = pd.read_sql(text(SQL_SIN_RESPUESTA), conn)
    if materias_ids is not None:
        df = df[df["materia_id"].isin(materias_ids)]
    return df.drop(columns="materia_id").reset_index(drop=True)


def cargar(materias_ids: list[int] | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    with engine.connect() as conn:
        msgs = pd.read_sql(text(SQL_MENSAJES), conn)
        resp = pd.read_sql(text(SQL_RESPUESTAS), conn)
    if materias_ids is not None:
        msgs = msgs[msgs["materia_id"].isin(materias_ids)]
        resp = resp[resp["materia_id"].isin(materias_ids)]
    for df in (msgs, resp):
        df["fecha"] = pd.to_datetime(df["fecha"], utc=True)
    resp = resp.assign(es_correcta=resp["es_correcta"].astype(bool))
    return msgs.reset_index(drop=True), resp.reset_index(drop=True)


def resumen(msgs: pd.DataFrame, resp: pd.DataFrame) -> dict:
    return {
        "preguntas": int((msgs["rol"] == "user").sum()),
        "alumnos_activos": int(msgs["alumno_id"].nunique()),
        "quizzes_respondidos": int(len(resp)),
        "pct_aciertos": float(resp["es_correcta"].mean() * 100) if len(resp) else 0.0,
    }


def preguntas_por_tema(msgs: pd.DataFrame) -> pd.DataFrame:
    u = msgs[msgs["rol"] == "user"]
    return u.groupby("tema").size().rename("preguntas").sort_values(ascending=False).reset_index()


def aciertos_por_tema(resp: pd.DataFrame) -> pd.DataFrame:
    if resp.empty:
        return pd.DataFrame(columns=["tema", "intentos", "% aciertos"])
    g = resp.groupby("tema")["es_correcta"].agg(intentos="count", aciertos="sum")
    g["% aciertos"] = (g["aciertos"] / g["intentos"] * 100).round(1)
    return g.drop(columns="aciertos").reset_index()


def alumnos_mas_activos(msgs: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    u = msgs[msgs["rol"] == "user"]
    return u.groupby("alumno").size().rename("preguntas").sort_values(ascending=False).head(top).reset_index()


def preguntas_mas_falladas(resp: pd.DataFrame, top: int = 10) -> pd.DataFrame:
    if resp.empty:
        return pd.DataFrame(columns=["pregunta", "intentos", "errores", "% error"])
    g = resp.groupby("pregunta")["es_correcta"].agg(intentos="count", aciertos="sum")
    g["errores"] = g["intentos"] - g["aciertos"]
    g["% error"] = (g["errores"] / g["intentos"] * 100).round(1)
    g = g[g["errores"] > 0].drop(columns="aciertos")
    return g.sort_values(["errores", "% error"], ascending=False).head(top).reset_index()


def uso_por_fecha(msgs: pd.DataFrame) -> pd.DataFrame:
    u = msgs[msgs["rol"] == "user"]
    if u.empty:
        return pd.DataFrame(columns=["preguntas"])
    return u.groupby(u["fecha"].dt.date).size().rename("preguntas").to_frame()
