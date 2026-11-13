from sqlalchemy import select

from core.db import get_session
from models.schema import Materia, Quiz, RespuestaQuiz, Tema, Unidad

# Cuántas respuestas recientes cuentan y cuántas se necesitan para opinar
VENTANA = 10
MIN_INTENTOS = 3
UMBRAL_APOYO = 50      # menos de este % de aciertos: al alumno le cuesta
UMBRAL_AVANZADO = 80   # este % o más: domina el tema


def _nivel(total: int, pct: float | None) -> str:
    if total < MIN_INTENTOS:
        return "normal"
    if pct < UMBRAL_APOYO:
        return "apoyo"
    return "avanzado" if pct >= UMBRAL_AVANZADO else "normal"


def resumen_alumno(alumno_id: int) -> list[dict]:
    # Aciertos del alumno en cada tema donde ha respondido quizzes (últimos VENTANA por tema).
    with get_session() as s:
        filas = s.execute(
            select(Tema.nombre, Materia.nombre, RespuestaQuiz.es_correcta, Quiz.tema_id)
            .join(Quiz, Quiz.id == RespuestaQuiz.quiz_id)
            .join(Tema, Tema.id == Quiz.tema_id)
            .join(Unidad, Unidad.id == Tema.unidad_id)
            .join(Materia, Materia.id == Unidad.materia_id)
            .where(RespuestaQuiz.alumno_id == alumno_id)
            .order_by(RespuestaQuiz.id.desc())
        ).all()
    por_tema: dict[int, dict] = {}
    for tema, materia, ok, tema_id in filas:
        d = por_tema.setdefault(tema_id, {"tema": tema, "materia": materia, "res": []})
        if len(d["res"]) < VENTANA:
            d["res"].append(bool(ok))
    salida = []
    for d in por_tema.values():
        total, aciertos = len(d["res"]), sum(d["res"])
        pct = round(aciertos / total * 100)
        salida.append({"tema": d["tema"], "materia": d["materia"], "intentos": total,
                       "aciertos": aciertos, "porcentaje": pct, "nivel": _nivel(total, pct)})
    return sorted(salida, key=lambda r: r["porcentaje"])


def progreso_tema(alumno_id: int, tema_id: int) -> dict:
    # Aciertos del alumno en los últimos quizzes de un tema y el nivel que le corresponde.
    with get_session() as s:
        filas = s.scalars(
            select(RespuestaQuiz.es_correcta)
            .join(Quiz, Quiz.id == RespuestaQuiz.quiz_id)
            .where(RespuestaQuiz.alumno_id == alumno_id, Quiz.tema_id == tema_id)
            .order_by(RespuestaQuiz.id.desc())
            .limit(VENTANA)
        ).all()
    total = len(filas)
    aciertos = sum(1 for f in filas if f)
    pct = round(aciertos / total * 100) if total else None
    if total < MIN_INTENTOS:
        nivel = "normal"
    elif pct < UMBRAL_APOYO:
        nivel = "apoyo"
    elif pct >= UMBRAL_AVANZADO:
        nivel = "avanzado"
    else:
        nivel = "normal"
    return {"total": total, "aciertos": aciertos, "porcentaje": pct, "nivel": nivel}
