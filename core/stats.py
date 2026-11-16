# Estadísticas para el maestro 
import re
from io import BytesIO

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


def material_faltante(sin_resp: pd.DataFrame, minimo_alumnos: int = 2) -> pd.DataFrame:
    """Temas donde varios alumnos distintos preguntaron algo que el material no cubre.

    Una sola pregunta sin respuesta puede ser un capricho; que varios alumnos coincidan en el mismo tema indica
    que falta contenido. Devuelve materia, tema, alumnos (distintos), preguntas y un ejemplo (la más reciente).
    """
    columnas = ["materia", "tema", "alumnos", "preguntas", "ejemplo"]
    if sin_resp.empty:
        return pd.DataFrame(columns=columnas)
    g = (sin_resp.groupby(["materia", "tema"])
         .agg(alumnos=("alumno", "nunique"), preguntas=("pregunta", "count"), ejemplo=("pregunta", "first"))
         .reset_index())
    g = g[g["alumnos"] >= minimo_alumnos].sort_values(["alumnos", "preguntas"], ascending=False)
    return g[columnas].reset_index(drop=True)


def _nombre_hoja(nombre: str, usados: set[str]) -> str:
    limpio = re.sub(r"[\\/*?:\[\]]", " ", nombre).strip()[:31] or "Hoja"
    base, n = limpio, 2
    while limpio.lower() in usados:  # Excel no admite dos hojas con el mismo nombre
        limpio = f"{base[:28]} {n}"
        n += 1
    usados.add(limpio.lower())
    return limpio


def exportar_excel(hojas: dict[str, pd.DataFrame]) -> bytes:
    """Libro de Excel (.xlsx) con una hoja por tabla: encabezado con color, filtros y columnas ajustadas."""
    from openpyxl.styles import Alignment, Font, PatternFill

    salida, usados = BytesIO(), set()
    with pd.ExcelWriter(salida, engine="openpyxl") as libro:
        for nombre, df in (hojas or {"Resumen": pd.DataFrame()}).items():
            df = df.copy()
            for col in df.columns:  # Excel no guarda zonas horarias: se conserva la hora local
                if isinstance(df[col].dtype, pd.DatetimeTZDtype):
                    df[col] = df[col].dt.tz_localize(None)
            hoja = _nombre_hoja(nombre, usados)
            df.to_excel(libro, sheet_name=hoja, index=False)
            ws = libro.sheets[hoja]
            for celda in ws[1]:
                celda.font = Font(bold=True, color="FFFFFF")
                celda.fill = PatternFill("solid", fgColor="0B3D91")
                celda.alignment = Alignment(vertical="center")
            ws.freeze_panes = "A2"
            if ws.max_row >= 1 and ws.max_column >= 1:
                ws.auto_filter.ref = ws.dimensions
            for i, col in enumerate(df.columns, 1):
                largo = max([len(str(col))] + [len(str(v)) for v in df[col].head(200)])
                ws.column_dimensions[ws.cell(1, i).column_letter].width = min(60, max(10, largo + 2))
    return salida.getvalue()


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


def resumen_por_alumno(msgs: pd.DataFrame, resp: pd.DataFrame, minutos: dict[str, float]) -> pd.DataFrame:
    # Una fila por alumno con su actividad, para exportar a CSV.
    nombres = sorted(set(msgs["alumno"]) | set(resp["alumno"]))
    filas = []
    for n in nombres:
        preguntas = int(((msgs["alumno"] == n) & (msgs["rol"] == "user")).sum())
        r = resp[resp["alumno"] == n]
        filas.append({"alumno": n, "preguntas": preguntas, "quizzes": int(len(r)),
                      "% aciertos": round(float(r["es_correcta"].mean() * 100), 1) if len(r) else None,
                      "minutos en la app": minutos.get(n, 0.0)})
    return pd.DataFrame(filas, columns=["alumno", "preguntas", "quizzes", "% aciertos", "minutos en la app"])


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
