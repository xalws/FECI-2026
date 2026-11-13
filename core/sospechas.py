# Señales de actividad a revisar. Son indicios, no prueba de trampa.
import pandas as pd
from sqlalchemy import text

from core.db import engine

MIN_SEG = 5               # mínimo de segundos para leer y responder un quiz
SEG_POR_PALABRA = 0.3     # tiempo de lectura extra según el largo de la pregunta
MAX_MIN_SEG = 15
RAPIDAS_MIN = 3           # cuántas respuestas rápidas activan la alerta
RAFAGA_N, RAFAGA_SEG = 5, 60   # 5 respuestas en 60 s
SALTO_BAJO, SALTO_ALTO = 0.30, 0.80   # mejora brusca: de <=30% a >=80% en 5 respuestas

SQL = """
SELECT r.alumno_id, u.nombre AS alumno, r.es_correcta, r.fecha AS fecha_resp,
       q.fecha AS fecha_quiz, q.pregunta, q.opciones, ma.id AS materia_id
FROM respuestas_quiz r
JOIN quizzes q ON q.id = r.quiz_id
JOIN usuarios u ON u.id = r.alumno_id
JOIN temas t ON t.id = q.tema_id
JOIN unidades un ON un.id = t.unidad_id
JOIN materias ma ON ma.id = un.materia_id
"""


def _segundos_minimos(pregunta: str, opciones) -> float:
    palabras = len(f"{pregunta} {opciones}".split())
    return min(MAX_MIN_SEG, max(MIN_SEG, palabras * SEG_POR_PALABRA))


def evaluar(df: pd.DataFrame) -> pd.DataFrame:
    # Recibe respuestas (columnas de SQL) y devuelve un renglón por alumno con alertas.
    columnas = ["alumno", "respuestas", "rápidas", "motivos"]
    if df.empty:
        return pd.DataFrame(columns=columnas)
    df = df.copy()
    df["fecha_resp"] = pd.to_datetime(df["fecha_resp"], utc=True)
    df["fecha_quiz"] = pd.to_datetime(df["fecha_quiz"], utc=True)
    df["seg"] = (df["fecha_resp"] - df["fecha_quiz"]).dt.total_seconds()
    df["min_seg"] = [_segundos_minimos(p, o) for p, o in zip(df["pregunta"], df["opciones"])]
    df["rapida"] = df["seg"] < df["min_seg"]

    filas = []
    for _, g in df.sort_values("fecha_resp").groupby("alumno_id"):
        motivos = []
        n_rapidas = int(g["rapida"].sum())
        if n_rapidas >= RAPIDAS_MIN:
            motivos.append(f"{n_rapidas} respuestas más rápidas de lo que toma leer la pregunta")

        t = g["fecha_resp"].tolist()
        if any((t[i + RAFAGA_N - 1] - t[i]).total_seconds() <= RAFAGA_SEG
               for i in range(len(t) - RAFAGA_N + 1)):
            motivos.append(f"{RAFAGA_N} respuestas en menos de {RAFAGA_SEG} segundos")

        ok = g["es_correcta"].astype(bool).tolist()
        if len(ok) >= 10:
            antes, ahora = ok[-10:-5], ok[-5:]
            if sum(antes) / 5 <= SALTO_BAJO and sum(ahora) / 5 >= SALTO_ALTO:
                motivos.append("mejora brusca: de casi todo mal a casi todo bien en las últimas 5")

        if motivos:
            filas.append({"alumno": g["alumno"].iloc[0], "respuestas": len(g),
                          "rápidas": n_rapidas, "motivos": "; ".join(motivos)})
    return pd.DataFrame(filas, columns=columnas)


def cargar_y_evaluar(materias_ids: list[int] | None = None) -> pd.DataFrame:
    with engine.connect() as conn:
        df = pd.read_sql(text(SQL), conn)
    if materias_ids is not None:
        df = df[df["materia_id"].isin(materias_ids)]
    return evaluar(df)
