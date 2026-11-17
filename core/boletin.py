"""Boletín semanal de una clase para su maestro: qué pasó en los últimos 7 días y a quién conviene buscar.

`cargar` lee los datos de la base; `resumir` los convierte en el boletín (es puro, así se prueba sin base);
`como_texto` y `como_excel` lo dejan listo para pegar en un mensaje o abrir en una hoja de cálculo.
"""
from datetime import datetime, timedelta, timezone, tzinfo

import pandas as pd
from sqlalchemy import func, select

from core import actividad, stats, tareas
from core.clases import ACTIVO, _puede_gestionar
from core.db import get_session
from models.schema import (Actividad, Clase, Conversacion, Inscripcion, IntentoEjercicio, Materia, Mensaje,
                           PreguntaSinRespuesta, Quiz, RespuestaQuiz, Tema, Unidad, Usuario)

DIAS = 7
MIN_QUIZZES_APOYO = 3        # con menos respuestas no se juzga el desempeño
BAJO = 50.0                  # % de aciertos por debajo del cual el alumno necesita apoyo
ALTO = 85.0                  # % de aciertos desde el cual destaca (con al menos MIN_QUIZZES_DESTACADO respuestas)
MIN_QUIZZES_DESTACADO = 5
MIN_INTENTOS_TEMA = 3        # intentos mínimos para llamar «flojo» a un tema
TEMA_FLOJO = 60.0

ESTADOS = ("Necesita apoyo", "Sin actividad", "Aún no entra", "Destacado", "Al día")


def _utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _pct(correctas: int, total: int) -> float | None:
    return round(100 * correctas / total) if total else None


def cargar(usuario_id: int, clase_id: int, ahora: datetime | None = None) -> dict | None:
    """Datos crudos de las últimas dos semanas (la actual y la anterior, para comparar). None si no es su clase."""
    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(days=2 * DIAS)
    with get_session() as s:
        clase = s.get(Clase, clase_id)
        if clase is None or not _puede_gestionar(s, usuario_id, clase):
            return None
        materia = s.get(Materia, clase.materia_id)
        alumnos = {a: n for a, n in s.execute(
            select(Usuario.id, Usuario.nombre).join(Inscripcion, Inscripcion.alumno_id == Usuario.id)
            .where(Inscripcion.clase_id == clase_id, Inscripcion.estado == ACTIVO).order_by(Usuario.nombre))}
        temas = {t: n for t, n in s.execute(select(Tema.id, Tema.nombre).join(Unidad, Unidad.id == Tema.unidad_id)
                                            .where(Unidad.materia_id == clase.materia_id))}
        raw = {"clase": {"id": clase.id, "nombre": clase.nombre, "materia": materia.nombre if materia else ""},
               "alumnos": alumnos, "temas": temas, "mensajes": [], "quizzes": [], "ejercicios": [], "marcas": [],
               "ultima": {}, "sin_respuesta": [], "tareas": []}
        if alumnos:
            ids, ids_temas = list(alumnos), list(temas)
            raw["mensajes"] = [tuple(f) for f in s.execute(
                select(Conversacion.alumno_id, Mensaje.fecha).join(Conversacion, Conversacion.id == Mensaje.conversacion_id)
                .where(Mensaje.rol == "user", Conversacion.alumno_id.in_(ids), Conversacion.tema_id.in_(ids_temas),
                       Mensaje.fecha >= desde))]
            raw["quizzes"] = [tuple(f) for f in s.execute(
                select(RespuestaQuiz.alumno_id, Quiz.tema_id, RespuestaQuiz.es_correcta, RespuestaQuiz.fecha)
                .join(Quiz, Quiz.id == RespuestaQuiz.quiz_id)
                .where(RespuestaQuiz.alumno_id.in_(ids), Quiz.tema_id.in_(ids_temas), RespuestaQuiz.fecha >= desde))]
            raw["ejercicios"] = [tuple(f) for f in s.execute(
                select(IntentoEjercicio.alumno_id, IntentoEjercicio.fecha)
                .where(IntentoEjercicio.alumno_id.in_(ids), IntentoEjercicio.tema_id.in_(ids_temas),
                       IntentoEjercicio.fecha >= desde))]
            raw["marcas"] = [tuple(f) for f in s.execute(select(Actividad.usuario_id, Actividad.fecha)
                                                         .where(Actividad.usuario_id.in_(ids), Actividad.fecha >= desde))]
            raw["ultima"] = {u: f for u, f in s.execute(select(Actividad.usuario_id, func.max(Actividad.fecha))
                                                        .where(Actividad.usuario_id.in_(ids)).group_by(Actividad.usuario_id))}
            raw["sin_respuesta"] = [tuple(f) for f in s.execute(
                select(PreguntaSinRespuesta.tema_id, PreguntaSinRespuesta.alumno_id, PreguntaSinRespuesta.fecha)
                .where(PreguntaSinRespuesta.alumno_id.in_(ids), PreguntaSinRespuesta.tema_id.in_(ids_temas),
                       PreguntaSinRespuesta.fecha >= desde))]
    raw["tareas"] = tareas.tareas_de_clase(usuario_id, clase_id)
    return raw


def _estado(quizzes: int, correctas: int, activo: bool, nunca: bool) -> tuple[str, str]:
    """(estado, motivo) de un alumno según su semana."""
    pct = _pct(correctas, quizzes)
    if quizzes >= MIN_QUIZZES_APOYO and pct < BAJO:
        return "Necesita apoyo", f"Acertó {pct:.0f}% de {quizzes} preguntas de quiz."
    if nunca:
        return "Aún no entra", "Todavía no tiene actividad registrada."
    if not activo:
        return "Sin actividad", "No estudió en la semana."
    if quizzes >= MIN_QUIZZES_DESTACADO and pct >= ALTO:
        return "Destacado", f"Acertó {pct:.0f}% de {quizzes} preguntas de quiz."
    return "Al día", ""


def resumir(raw: dict, ahora: datetime | None = None, zona: tzinfo = timezone.utc) -> dict:
    """El boletín: totales de la semana contra la anterior, una fila por alumno, temas flojos, tareas y material faltante."""
    ahora = ahora or datetime.now(timezone.utc)
    inicio, previo = ahora - timedelta(days=DIAS), ahora - timedelta(days=2 * DIAS)

    def semana(fecha) -> bool:
        return _utc(fecha) >= inicio

    def previa(fecha) -> bool:
        return previo <= _utc(fecha) < inicio

    alumnos, temas = raw["alumnos"], raw["temas"]
    marcas_de: dict[int, list] = {a: [] for a in alumnos}
    for uid, f in raw["marcas"]:
        if uid in marcas_de and semana(f):
            marcas_de[uid].append(_utc(f))

    filas, activos_prev = [], set()
    tot = {"preguntas": 0, "quizzes": 0, "correctas": 0, "minutos": 0.0}
    prev = {"preguntas": 0, "quizzes": 0, "correctas": 0}
    for a in alumnos:
        msgs = [_utc(f) for u, f in raw["mensajes"] if u == a and semana(f)]
        quiz = [(c, _utc(f)) for u, _t, c, f in raw["quizzes"] if u == a and semana(f)]
        ejer = [_utc(f) for u, f in raw["ejercicios"] if u == a and semana(f)]
        eventos = msgs + [f for _, f in quiz] + ejer + marcas_de[a]
        # actividad de la semana anterior (solo para comparar cuántos alumnos estuvieron activos)
        if (any(u == a and previa(f) for u, f in raw["mensajes"]) or any(u == a and previa(f) for u, _t, _c, f in raw["quizzes"])
                or any(u == a and previa(f) for u, f in raw["ejercicios"]) or any(u == a and previa(f) for u, f in raw["marcas"])):
            activos_prev.add(a)
        prev["preguntas"] += sum(1 for u, f in raw["mensajes"] if u == a and previa(f))
        previas = [c for u, _t, c, f in raw["quizzes"] if u == a and previa(f)]
        prev["quizzes"] += len(previas)
        prev["correctas"] += sum(1 for c in previas if c)

        correctas = sum(1 for c, _ in quiz if c)
        minutos = round(actividad.segundos_de_uso(marcas_de[a]) / 60, 1)
        ultima_vez = max(eventos + ([_utc(raw["ultima"][a])] if a in raw["ultima"] else []), default=None)
        estado, motivo = _estado(len(quiz), correctas, bool(eventos), ultima_vez is None)
        if estado == "Sin actividad" and ultima_vez is not None:
            motivo = f"Su última actividad fue el {ultima_vez.astimezone(zona):%d/%m}."
        dias = {f.astimezone(zona).date() for f in eventos}
        filas.append({"alumno": alumnos[a], "estado": estado, "motivo": motivo, "preguntas": len(msgs),
                      "quizzes": len(quiz), "aciertos": _pct(correctas, len(quiz)), "ejercicios": len(ejer),
                      "días activos": len(dias), "minutos": minutos,
                      "última vez": ultima_vez.astimezone(zona).date() if ultima_vez else None})
        tot["preguntas"] += len(msgs)
        tot["quizzes"] += len(quiz)
        tot["correctas"] += correctas
        tot["minutos"] += minutos
    orden = {e: i for i, e in enumerate(ESTADOS)}
    filas.sort(key=lambda f: (orden[f["estado"]], f["alumno"]))

    # temas donde más fallaron esta semana
    por_tema: dict[int, list[bool]] = {}
    for _u, t, c, f in raw["quizzes"]:
        if semana(f):
            por_tema.setdefault(t, []).append(bool(c))
    flojos = sorted(({"tema": temas.get(t, "—"), "intentos": len(v), "% aciertos": _pct(sum(v), len(v))}
                     for t, v in por_tema.items() if len(v) >= MIN_INTENTOS_TEMA and _pct(sum(v), len(v)) < TEMA_FLOJO),
                    key=lambda d: (d["% aciertos"], -d["intentos"]))[:5]

    # tareas que vencieron esta semana o vencen en los próximos días
    horizonte = ahora + timedelta(days=DIAS)
    tareas_sem = []
    for t in raw["tareas"]:
        limite = _utc(t["fecha_limite"])
        if inicio <= limite <= horizonte:
            tareas_sem.append({"tema": t["tema"], "tarea": t["descripcion"], "límite": limite.astimezone(zona).date(),
                               "hechas": t["hechas"], "alumnos": t["alumnos"], "vencida": limite < ahora})
    tareas_sem.sort(key=lambda t: t["límite"])

    # preguntas que el tutor no pudo contestar (falta material)
    conteo: dict[int, int] = {}
    for t, _a, f in raw["sin_respuesta"]:
        if semana(f):
            conteo[t] = conteo.get(t, 0) + 1
    sin_resp = sorted(({"tema": temas.get(t, "—"), "preguntas": n} for t, n in conteo.items()),
                      key=lambda d: -d["preguntas"])

    activos = sum(1 for f in filas if f["estado"] not in ("Sin actividad", "Aún no entra"))
    pct_actual, pct_previo = _pct(tot["correctas"], tot["quizzes"]), _pct(prev["correctas"], prev["quizzes"])
    boletin = {
        "clase": raw["clase"]["nombre"], "materia": raw["clase"]["materia"],
        "desde": inicio.astimezone(zona).date(), "hasta": ahora.astimezone(zona).date(),
        "total_alumnos": len(alumnos),
        "semana": {"activos": activos, "preguntas": tot["preguntas"], "quizzes": tot["quizzes"], "aciertos": pct_actual,
                   "minutos": round(tot["minutos"], 1)},
        "anterior": {"activos": len(activos_prev), "preguntas": prev["preguntas"], "quizzes": prev["quizzes"],
                     "aciertos": pct_previo},
        "alumnos": filas,
        "necesitan_apoyo": [f for f in filas if f["estado"] in ("Necesita apoyo", "Sin actividad", "Aún no entra")],
        "destacados": [f for f in filas if f["estado"] == "Destacado"],
        "temas_flojos": flojos, "tareas": tareas_sem, "sin_respuesta": sin_resp,
    }
    boletin["frases"] = _frases(boletin)
    return boletin


def _cambio(actual: int, antes: int) -> str:
    if actual == antes:
        return "igual que la semana anterior"
    return f"{'+' if actual > antes else '−'}{abs(actual - antes)} contra la semana anterior"


def _frases(b: dict) -> list[str]:
    """Lo más importante de la semana, en oraciones."""
    s, p, total = b["semana"], b["anterior"], b["total_alumnos"]
    if not total:
        return ["La clase todavía no tiene alumnos."]
    frases = [f"{s['activos']} de {total} {'alumno estuvo activo' if total == 1 else 'alumnos estuvieron activos'} "
              f"({_cambio(s['activos'], p['activos'])})."]
    if s["preguntas"] or s["quizzes"]:
        acierto = f" con {s['aciertos']:.0f}% de aciertos" if s["aciertos"] is not None else ""
        frases.append(f"Hicieron {s['preguntas']} preguntas al tutor ({_cambio(s['preguntas'], p['preguntas'])}) y "
                      f"respondieron {s['quizzes']} preguntas de quiz{acierto}.")
    else:
        frases.append("Nadie hizo preguntas ni quizzes en la semana.")
    if b["temas_flojos"]:
        t = b["temas_flojos"][0]
        frases.append(f"El tema más flojo fue «{t['tema']}»: {t['% aciertos']:.0f}% de aciertos en {t['intentos']} respuestas.")
    apoyo = b["necesitan_apoyo"]
    if apoyo:
        frases.append(f"{len(apoyo)} {'alumno merece' if len(apoyo) == 1 else 'alumnos merecen'} que los busques: "
                      + ", ".join(f["alumno"] for f in apoyo[:5]) + ("…" if len(apoyo) > 5 else "") + ".")
    vencidas = [t for t in b["tareas"] if t["vencida"]]
    for t in vencidas[:3]:
        frases.append(f"Tarea vencida «{t['tarea']}» ({t['tema']}): la cumplieron {t['hechas']} de {t['alumnos']}.")
    proximas = [t for t in b["tareas"] if not t["vencida"]]
    if proximas:
        t = proximas[0]
        frases.append(f"Próxima tarea en vencer: «{t['tarea']}» el {t['límite']:%d/%m}; la llevan {t['hechas']} de {t['alumnos']}.")
    if b["sin_respuesta"]:
        total = sum(d["preguntas"] for d in b["sin_respuesta"])
        # cada tema con su número: «6 preguntas; falta material sobre X» hacía creer que las 6 eran de X
        detalle = ", ".join(f"«{d['tema']}» ({d['preguntas']})" for d in b["sin_respuesta"][:3])
        mas = "…" if len(b["sin_respuesta"]) > 3 else ""
        frases.append(f"El tutor no pudo contestar {total} {'pregunta' if total == 1 else 'preguntas'} por falta de "
                      f"material: {detalle}{mas}.")
    if b["destacados"]:
        frases.append("Destacaron: " + ", ".join(f["alumno"] for f in b["destacados"][:5]) + ".")
    return frases


def como_texto(b: dict) -> str:
    """El boletín en texto plano, para pegarlo en un correo o un mensaje."""
    lineas = [f"Boletín semanal · {b['clase']} ({b['materia']})", f"Del {b['desde']:%d/%m/%Y} al {b['hasta']:%d/%m/%Y}", ""]
    lineas += [f"• {f}" for f in b["frases"]]
    if b["necesitan_apoyo"]:
        lineas += ["", "A quién buscar:"] + [f"  - {f['alumno']}: {f['motivo']}" for f in b["necesitan_apoyo"]]
    if b["temas_flojos"]:
        lineas += ["", "Temas con más errores:"] + [f"  - {t['tema']}: {t['% aciertos']:.0f}% ({t['intentos']} respuestas)"
                                                     for t in b["temas_flojos"]]
    return "\n".join(lineas) + "\n"


def como_excel(b: dict) -> bytes:
    s, p = b["semana"], b["anterior"]
    resumen = pd.DataFrame([
        ("Alumnos activos", s["activos"], p["activos"]), ("Preguntas al tutor", s["preguntas"], p["preguntas"]),
        ("Quizzes respondidos", s["quizzes"], p["quizzes"]), ("% de aciertos", s["aciertos"], p["aciertos"])],
        columns=["indicador", "esta semana", "semana anterior"])
    hojas = {"Resumen": resumen,
             "Alumnos": pd.DataFrame(b["alumnos"]).rename(columns={"aciertos": "% aciertos"}),
             "Temas flojos": pd.DataFrame(b["temas_flojos"], columns=["tema", "intentos", "% aciertos"]),
             "Tareas": pd.DataFrame(b["tareas"], columns=["tema", "tarea", "límite", "hechas", "alumnos", "vencida"]),
             "Material faltante": pd.DataFrame(b["sin_respuesta"], columns=["tema", "preguntas"])}
    return stats.exportar_excel(hojas)


def generar(usuario_id: int, clase_id: int, zona: tzinfo = timezone.utc, ahora: datetime | None = None) -> dict | None:
    raw = cargar(usuario_id, clase_id, ahora)
    return None if raw is None else resumir(raw, ahora, zona)
