"""Competencia sana dentro de una clase: XP, ranking y perfil que ven los compañeros.

Se compara el ESFUERZO (XP, racha, minutos y logros); nunca las calificaciones ni los errores. Los XP son los de
`core/niveles.py`: cada respuesta correcta suma tantos XP como su dificultad y los ejercicios suman de 0 a 3.
Un alumno solo ve el perfil de quien comparte una clase con él (o el suyo); el maestro ve el de los alumnos de
sus clases y el administrador el de cualquiera.
"""
from datetime import date, datetime, timedelta, timezone, tzinfo

from sqlalchemy import select

from core import actividad, clases, logros, niveles
from core.db import get_session
from models.schema import Inscripcion, IntentoEjercicio, Materia, Quiz, RespuestaQuiz, Tema, Unidad, Usuario

# XP acumulados mínimos -> título del alumno
TITULOS = [(0, "Novato"), (25, "Aprendiz"), (75, "Estudioso"), (150, "Avanzado"), (300, "Experto"), (600, "Maestro"),
           (1200, "Leyenda")]
SEMANAS_GRAFICA = 8


def nivel_global(xp: int) -> dict:
    """Título del alumno según sus XP totales y cuánto le falta para el siguiente."""
    indice = max(i for i, (minimo, _) in enumerate(TITULOS) if xp >= minimo)
    minimo, nombre = TITULOS[indice]
    siguiente = TITULOS[indice + 1][0] if indice + 1 < len(TITULOS) else None
    porcentaje = 100 if siguiente is None else round((xp - minimo) / (siguiente - minimo) * 100)
    return {"numero": indice + 1, "nombre": nombre, "xp": xp, "siguiente": siguiente, "porcentaje": porcentaje}


def _utc(f: datetime) -> datetime:
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)  # SQLite devuelve las fechas sin zona


def eventos_xp(s, alumno_ids: list[int]) -> list[tuple[int, datetime, int]]:
    """(alumno, cuándo, XP) de cada respuesta correcta y cada ejercicio calificado."""
    if not alumno_ids:
        return []
    eventos = []
    for alumno, fecha, dificultad, ok in s.execute(
            select(RespuestaQuiz.alumno_id, RespuestaQuiz.fecha, Quiz.dificultad, RespuestaQuiz.es_correcta)
            .join(Quiz, Quiz.id == RespuestaQuiz.quiz_id).where(RespuestaQuiz.alumno_id.in_(alumno_ids))):
        xp = niveles.xp_respuesta(dificultad, bool(ok))
        if xp:
            eventos.append((alumno, _utc(fecha), xp))
    for alumno, fecha, puntaje in s.execute(
            select(IntentoEjercicio.alumno_id, IntentoEjercicio.fecha, IntentoEjercicio.puntaje)
            .where(IntentoEjercicio.alumno_id.in_(alumno_ids))):
        xp = niveles.xp_ejercicio(puntaje)
        if xp:
            eventos.append((alumno, _utc(fecha), xp))
    return eventos


def lunes_de(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def xp_por_semana(eventos: list[tuple[datetime, int]], zona: tzinfo, hoy: date,
                  semanas: int = SEMANAS_GRAFICA) -> list[tuple[date, int]]:
    """XP de cada una de las últimas `semanas` semanas (de lunes a domingo, hora local), de la más antigua a la actual."""
    primera = lunes_de(hoy) - timedelta(weeks=semanas - 1)
    por_semana = {primera + timedelta(weeks=i): 0 for i in range(semanas)}
    for fecha, xp in eventos:
        lunes = lunes_de(fecha.astimezone(zona).date())
        if lunes in por_semana:
            por_semana[lunes] += xp
    return list(por_semana.items())


def ordenar_ranking(filas: list[dict]) -> list[dict]:
    """Ordena por XP (de mayor a menor, luego por nombre) y numera: los empates comparten posición."""
    filas = sorted(filas, key=lambda f: (-f["xp"], f["nombre"].lower()))
    posicion = 0
    for i, f in enumerate(filas):
        if i == 0 or f["xp"] != filas[i - 1]["xp"]:
            posicion = i + 1
        f["posicion"] = posicion
    return filas


def ranking(clase_id: int, zona: tzinfo, periodo: str = "total", hoy: date | None = None) -> list[dict]:
    """Todos los alumnos activos de la clase ordenados por XP (`periodo`: «total» o «semana» = la semana actual)."""
    hoy = hoy or datetime.now(zona).date()
    with get_session() as s:
        miembros = s.execute(select(Usuario.id, Usuario.nombre).join(Inscripcion, Inscripcion.alumno_id == Usuario.id)
                             .where(Inscripcion.clase_id == clase_id, Inscripcion.estado == clases.ACTIVO,
                                    Usuario.activo.is_(True))).all()
        eventos = eventos_xp(s, [m[0] for m in miembros])
    total = {m[0]: 0 for m in miembros}
    desde = lunes_de(hoy)
    for alumno, fecha, xp in eventos:
        if periodo == "semana" and fecha.astimezone(zona).date() < desde:
            continue
        total[alumno] += xp
    filas = [{"alumno_id": i, "nombre": n, "xp": total[i], "titulo": nivel_global(total[i])["nombre"]
              if periodo == "total" else None} for i, n in miembros]
    return ordenar_ranking(filas)


def puede_ver(viewer_id: int, alumno_id: int) -> bool:
    """¿Puede `viewer_id` ver el perfil de `alumno_id`? (él mismo, un compañero de clase, su maestro o el admin)."""
    with get_session() as s:
        viewer, alumno = s.get(Usuario, viewer_id), s.get(Usuario, alumno_id)
        if viewer is None or alumno is None or not viewer.activo or not alumno.activo or alumno.rol != "alumno":
            return False
        if viewer_id == alumno_id or viewer.rol == "admin":
            return True
        mias = select(Inscripcion.clase_id).where(Inscripcion.alumno_id == viewer_id, Inscripcion.estado == clases.ACTIVO)
        if viewer.rol == "alumno":
            return bool(s.scalar(select(Inscripcion.id).where(
                Inscripcion.alumno_id == alumno_id, Inscripcion.estado == clases.ACTIVO,
                Inscripcion.clase_id.in_(mias)).limit(1)))
        if viewer.rol == "maestro":
            from models.schema import Clase
            return bool(s.scalar(select(Inscripcion.id).join(Clase, Clase.id == Inscripcion.clase_id).where(
                Inscripcion.alumno_id == alumno_id, Inscripcion.estado == clases.ACTIVO,
                Clase.maestro_id == viewer_id).limit(1)))
    return False


def temas_dominados(alumno_id: int, minimo_nivel: int = 3, limite: int = 8) -> list[dict]:
    """Temas donde el alumno llegó a nivel Avanzado o Experto (los mejores primero)."""
    with get_session() as s:
        temas = ({r[0] for r in s.execute(select(Quiz.tema_id).join(RespuestaQuiz, RespuestaQuiz.quiz_id == Quiz.id)
                                          .where(RespuestaQuiz.alumno_id == alumno_id))}
                 | {r[0] for r in s.execute(select(IntentoEjercicio.tema_id).where(IntentoEjercicio.alumno_id == alumno_id))})
        if not temas:
            return []
        resp, ejer = niveles._por_tema(s, alumno_id, list(temas))
        nombres = {t: (tema, materia) for t, tema, materia in s.execute(
            select(Tema.id, Tema.nombre, Materia.nombre).join(Unidad, Unidad.id == Tema.unidad_id)
            .join(Materia, Materia.id == Unidad.materia_id).where(Tema.id.in_(temas)))}
    salida = []
    for t in temas:
        e = niveles.calcular_estado(resp.get(t, []), ejer.get(t, []))
        if e["nivel"] >= minimo_nivel:
            salida.append({"tema": nombres[t][0], "materia": nombres[t][1], "nivel": e["nivel"],
                           "nombre_nivel": e["nombre_nivel"], "xp": e["xp"]})
    return sorted(salida, key=lambda x: (-x["nivel"], -x["xp"], x["tema"]))[:limite]


def perfil_publico(viewer_id: int, alumno_id: int, zona: tzinfo, datos: dict | None = None,
                   hoy: date | None = None) -> dict | None:
    """Lo que se muestra de un alumno (None si quien pregunta no tiene permiso para verlo).

    `datos` es el resultado de `logros.datos_alumno` si quien llama ya lo calculó (evita repetir las consultas).
    """
    if not puede_ver(viewer_id, alumno_id):
        return None
    hoy = hoy or datetime.now(zona).date()
    datos = datos or logros.datos_alumno(alumno_id, zona, hoy)
    evaluados = logros.evaluar(datos)
    with get_session() as s:
        nombre = s.scalar(select(Usuario.nombre).where(Usuario.id == alumno_id))
        eventos = eventos_xp(s, [alumno_id])
    xp_total = sum(e[2] for e in eventos)
    semanas = xp_por_semana([(f, x) for _, f, x in eventos], zona, hoy)
    lunes = lunes_de(hoy)
    minutos_semana = round(sum(m for d, m in datos["minutos"].items() if d >= lunes))
    return {"alumno_id": alumno_id, "nombre": nombre, "nivel": nivel_global(xp_total), "xp_total": xp_total,
            "xp_semana": semanas[-1][1], "semanas": semanas, "racha": datos["racha"],
            "minutos_semana": minutos_semana, "resumen": logros.resumen(evaluados),
            "vitrina": logros.elegir_vitrina(evaluados, logros.vitrina_de(alumno_id)),
            "temas_dominados": temas_dominados(alumno_id), "logros": evaluados}


def solo_semanas(perfil: dict) -> list[dict]:
    """Serie de XP por semana lista para graficar."""
    return [{"semana": datetime.combine(d, datetime.min.time()), "xp": xp} for d, xp in perfil["semanas"]]
