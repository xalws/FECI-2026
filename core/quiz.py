from sqlalchemy import select

from core import llm, rag
from core.db import get_session
from models.schema import Quiz, RespuestaQuiz, Tema


def _preguntas_del_alumno(alumno_id: int, tema_id: int, solo_falladas: bool, limite: int) -> list[str]:
    # Preguntas recientes (sin repetir) que el alumno contestó en este tema, de la más nueva a la más vieja.
    q = (select(Quiz.pregunta).join(RespuestaQuiz, RespuestaQuiz.quiz_id == Quiz.id)
         .where(RespuestaQuiz.alumno_id == alumno_id, Quiz.tema_id == tema_id))
    if solo_falladas:
        q = q.where(RespuestaQuiz.es_correcta.is_(False))
    with get_session() as s:
        filas = s.scalars(q.order_by(RespuestaQuiz.id.desc()).limit(limite * 3)).all()
    unicas = list(dict.fromkeys(filas))
    return unicas[:limite]


def _fragmentos_para_quiz(tema_id: int, alumno_id: int | None) -> list[dict]:
    # Prioriza el material de las preguntas que el alumno falló y completa con fragmentos al azar.
    elegidos: list[dict] = []
    if alumno_id is not None:
        for pregunta in _preguntas_del_alumno(alumno_id, tema_id, solo_falladas=True, limite=2):
            elegidos += rag.buscar(tema_id, pregunta)[:1]
    elegidos += rag.chunks_aleatorios(tema_id, 3)
    vistos, unicos = set(), []
    for f in elegidos:
        if f["texto"] not in vistos:
            vistos.add(f["texto"])
            unicos.append(f)
    return unicos[:3]


def crear_quiz(tema_id: int, conversacion_id: int, dificultad: int = 2,
               alumno_id: int | None = None) -> dict | None:
    fragmentos = _fragmentos_para_quiz(tema_id, alumno_id)
    if not fragmentos:
        return None
    evitar = _preguntas_del_alumno(alumno_id, tema_id, solo_falladas=False, limite=5) if alumno_id else None
    with get_session() as s:
        objetivos = s.scalar(select(Tema.objetivos).where(Tema.id == tema_id)) or ""
    d = llm.generar_quiz(fragmentos, dificultad, evitar, objetivos)
    with get_session() as s:
        q = Quiz(conversacion_id=conversacion_id, tema_id=tema_id, pregunta=d["pregunta"],
                 opciones=d["opciones"], indice_correcto=d["indice_correcto"], explicacion=d["explicacion"],
                 dificultad=dificultad)
        s.add(q)
        s.flush()
        return {"id": q.id, "dificultad": dificultad, **d}


def evaluar(quiz_id: int, alumno_id: int, indice_elegido: int) -> dict:
    with get_session() as s:
        q = s.get(Quiz, quiz_id)
        correcta = indice_elegido == q.indice_correcto
        s.add(RespuestaQuiz(quiz_id=quiz_id, alumno_id=alumno_id,
                            indice_elegido=indice_elegido, es_correcta=correcta))
        return {"es_correcta": correcta, "indice_correcto": q.indice_correcto, "explicacion": q.explicacion}
