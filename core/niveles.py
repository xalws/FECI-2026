"""Sistema de niveles: puntos de experiencia (XP) por tema y avance por unidad según la retícula.

Cada respuesta correcta suma tantos XP como su dificultad (1 a 4), así que resolver preguntas difíciles
avanza más. Los ejercicios calificados suman de 0 a 3 XP. El nivel del tema sale de los XP acumulados, pero con
poca precisión (menos de 50% de aciertos en 4 o más intentos) no pasa de Principiante.
"""
import pandas as pd
from sqlalchemy import select

from core.db import get_session
from models.schema import Carrera, Cuatrimestre, IntentoEjercicio, Materia, Quiz, RespuestaQuiz, Tema, Unidad

NOMBRES = {0: "Sin empezar", 1: "Principiante", 2: "Intermedio", 3: "Avanzado", 4: "Experto"}
UMBRALES_XP = {1: 1, 2: 6, 3: 14, 4: 24}  # XP mínimos de cada nivel
XP_EXPERTO = UMBRALES_XP[4]
MIN_INTENTOS_PRECISION = 4
PRECISION_MIN = 0.5
DIFICULTAD_SIN_DATO = 2  # preguntas antiguas que no guardaron su dificultad


def xp_respuesta(dificultad: int | None, correcta: bool) -> int:
    return (dificultad or DIFICULTAD_SIN_DATO) if correcta else 0


def xp_ejercicio(puntaje: int) -> int:
    return max(0, min(3, puntaje // 3))


def nivel_por_xp(xp: int) -> int:
    return max((n for n, minimo in UMBRALES_XP.items() if xp >= minimo), default=0)


def calcular_estado(respuestas: list[tuple[int | None, bool]], puntajes_ejercicio: list[int]) -> dict:
    # respuestas: [(dificultad, acertó)], puntajes_ejercicio: [0..10]
    intentos = len(respuestas)
    aciertos = sum(1 for _, c in respuestas if c)
    xp = sum(xp_respuesta(d, c) for d, c in respuestas) + sum(xp_ejercicio(p) for p in puntajes_ejercicio)
    limitado = intentos >= MIN_INTENTOS_PRECISION and aciertos / intentos < PRECISION_MIN
    xp_efectivo = min(xp, UMBRALES_XP[2] - 1) if limitado else xp
    nivel = nivel_por_xp(xp_efectivo)
    return {"xp": xp, "xp_efectivo": xp_efectivo, "nivel": nivel, "nombre_nivel": NOMBRES[nivel],
            "intentos": intentos, "aciertos": aciertos, "limitado": limitado,
            "porcentaje": min(100, round(xp_efectivo / XP_EXPERTO * 100)),
            "siguiente_xp": UMBRALES_XP.get(nivel + 1)}


def _por_tema(s, alumno_id: int, tema_ids: list[int]) -> tuple[dict, dict]:
    resp: dict[int, list] = {}
    for tema_id, dif, ok in s.execute(
            select(Quiz.tema_id, Quiz.dificultad, RespuestaQuiz.es_correcta)
            .join(RespuestaQuiz, RespuestaQuiz.quiz_id == Quiz.id)
            .where(RespuestaQuiz.alumno_id == alumno_id, Quiz.tema_id.in_(tema_ids))):
        resp.setdefault(tema_id, []).append((dif, bool(ok)))
    ejer: dict[int, list] = {}
    for tema_id, puntaje in s.execute(
            select(IntentoEjercicio.tema_id, IntentoEjercicio.puntaje)
            .where(IntentoEjercicio.alumno_id == alumno_id, IntentoEjercicio.tema_id.in_(tema_ids))):
        ejer.setdefault(tema_id, []).append(puntaje)
    return resp, ejer


def estado_tema(alumno_id: int, tema_id: int) -> dict:
    with get_session() as s:
        resp, ejer = _por_tema(s, alumno_id, [tema_id])
    return calcular_estado(resp.get(tema_id, []), ejer.get(tema_id, []))


def _promedio_nivel(niveles: list[int]) -> int:
    return int(sum(niveles) / len(niveles)) if niveles else 0


def avance_materia(alumno_id: int, materia_id: int) -> dict:
    # Estado de cada tema agrupado por unidad, en el orden de la retícula.
    with get_session() as s:
        materia = s.get(Materia, materia_id)
        filas = s.execute(select(Unidad.id, Unidad.nombre, Tema.id, Tema.nombre)
                          .join(Tema, Tema.unidad_id == Unidad.id)
                          .where(Unidad.materia_id == materia_id).order_by(Unidad.id, Tema.id)).all()
        resp, ejer = _por_tema(s, alumno_id, [f[2] for f in filas]) if filas else ({}, {})
    unidades: dict[int, dict] = {}
    for uid, unombre, tid, tnombre in filas:
        u = unidades.setdefault(uid, {"id": uid, "nombre": unombre, "temas": []})
        u["temas"].append({"id": tid, "nombre": tnombre,
                           **calcular_estado(resp.get(tid, []), ejer.get(tid, []))})
    lista = list(unidades.values())
    todos = [t for u in lista for t in u["temas"]]
    for u in lista:
        u["porcentaje"] = round(sum(t["porcentaje"] for t in u["temas"]) / len(u["temas"]))
        u["nivel"] = _promedio_nivel([t["nivel"] for t in u["temas"]])
        u["nombre_nivel"] = NOMBRES[u["nivel"]]
    nivel = _promedio_nivel([t["nivel"] for t in todos])
    return {"materia": materia.nombre if materia else "", "unidades": lista,
            "porcentaje": round(sum(t["porcentaje"] for t in todos) / len(todos)) if todos else 0,
            "nivel": nivel, "nombre_nivel": NOMBRES[nivel], "xp": sum(t["xp"] for t in todos)}


def materias_disponibles() -> dict[int, str]:
    # Materias que ya tienen temas (id -> «Materia · Carrera · Cuatrimestre»).
    with get_session() as s:
        filas = s.execute(select(Materia.id, Materia.nombre, Carrera.nombre, Cuatrimestre.nombre)
                          .join(Cuatrimestre, Cuatrimestre.id == Materia.cuatrimestre_id)
                          .join(Carrera, Carrera.id == Cuatrimestre.carrera_id)
                          .where(Materia.id.in_(select(Unidad.materia_id)
                                                .join(Tema, Tema.unidad_id == Unidad.id)))
                          .order_by(Materia.nombre)).all()
    return {i: f"{m} · {c} · {q}" for i, m, c, q in filas}


def materias_con_actividad(alumno_id: int) -> set[int]:
    # Materias donde el alumno ya respondió preguntas o ejercicios.
    with get_session() as s:
        de_quizzes = set(s.scalars(
            select(Unidad.materia_id).join(Tema, Tema.unidad_id == Unidad.id)
            .join(Quiz, Quiz.tema_id == Tema.id).join(RespuestaQuiz, RespuestaQuiz.quiz_id == Quiz.id)
            .where(RespuestaQuiz.alumno_id == alumno_id)))
        de_ejercicios = set(s.scalars(
            select(Unidad.materia_id).join(Tema, Tema.unidad_id == Unidad.id)
            .join(IntentoEjercicio, IntentoEjercicio.tema_id == Tema.id)
            .where(IntentoEjercicio.alumno_id == alumno_id)))
    return de_quizzes | de_ejercicios


def tabla_avance(materia_id: int, alumnos: dict[int, str]) -> pd.DataFrame:
    # Una fila por alumno: nivel y % de avance de la materia y de cada unidad (para el maestro).
    filas = []
    for alumno_id, nombre in alumnos.items():
        av = avance_materia(alumno_id, materia_id)
        fila = {"alumno": nombre, "nivel": f"{av['nivel']} · {av['nombre_nivel']}", "% materia": av["porcentaje"]}
        for u in av["unidades"]:
            fila[f"% {u['nombre'][:30]}"] = u["porcentaje"]
        filas.append(fila)
    return pd.DataFrame(filas)
