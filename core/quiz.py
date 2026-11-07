"""Generar quizzes y evaluar las respuestas del alumno."""
from core import llm, rag
from core.db import get_session
from models.schema import Quiz, RespuestaQuiz


def crear_quiz(tema_id: int, conversacion_id: int) -> dict | None:
    """Crea un quiz con fragmentos al azar del tema. None si el tema no tiene material."""
    fragmentos = rag.chunks_aleatorios(tema_id, 3)
    if not fragmentos:
        return None
    d = llm.generar_quiz(fragmentos)
    with get_session() as s:
        q = Quiz(conversacion_id=conversacion_id, tema_id=tema_id, pregunta=d["pregunta"],
                 opciones=d["opciones"], indice_correcto=d["indice_correcto"], explicacion=d["explicacion"])
        s.add(q)
        s.flush()
        return {"id": q.id, **d}


def evaluar(quiz_id: int, alumno_id: int, indice_elegido: int) -> dict:
    with get_session() as s:
        q = s.get(Quiz, quiz_id)
        correcta = indice_elegido == q.indice_correcto
        s.add(RespuestaQuiz(quiz_id=quiz_id, alumno_id=alumno_id,
                            indice_elegido=indice_elegido, es_correcta=correcta))
        return {"es_correcta": correcta, "indice_correcto": q.indice_correcto, "explicacion": q.explicacion}
