"""Meta diaria de estudio y logros del alumno.

Todo se calcula con lo que la app ya guarda (actividad, respuestas de quiz, ejercicios, mensajes y clases). Lo único
que se guarda aparte es la meta diaria (`usuarios.meta_diaria_min`) y los logros que el alumno elige mostrar en su
perfil (`usuarios.vitrina`). Los logros no se «guardan»: se evalúan cada vez con reglas puras (`evaluar`), así que
un cambio de reglas se aplica solo.

Cada logro tiene 4 niveles: 1 Bronce, 2 Plata, 3 Élite (con el color de su categoría) y 4 Oro (el más alto).
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone, tzinfo

from sqlalchemy import case, func, select

from core import actividad, niveles
from core.cache import memo
from core.db import get_session
from models.schema import (Clase, Conversacion, IntentoEjercicio, Inscripcion, Mensaje, Quiz, RespuestaQuiz, Tema,
                           Unidad, Usuario)

METAS_MIN = (10, 15, 20, 30, 45, 60)
META_DEFECTO = 20
SEMANAS_CALENDARIO = 5
MAX_VITRINA = 6
NOMBRES_NIVEL = ["Sin conseguir", "Bronce", "Plata", "Élite", "Oro"]
NIVEL_MAXIMO = 4

# categoría -> (nombre, tono de color de core/estilo.py, ícono)
CATEGORIAS = {
    "constancia": ("Constancia", "ambar", "flame"),
    "dominio": ("Dominio", "indigo", "award"),
    "practica": ("Práctica", "violeta", "bulb"),
    "examenes": ("Exámenes", "verde", "target"),
    "exploracion": ("Exploración", "cielo", "search"),
    "comunidad": ("Comunidad", "rosa", "users"),
    "especiales": ("Especiales", "rojo", "sparkles"),
}

# (id, categoría, título, descripción con {n}, ícono, dato que se mide, umbrales de Bronce / Plata / Élite / Oro)
CATALOGO = [
    ("racha", "constancia", "Fuego constante", "Estudia {n} días seguidos", "flame", "racha_maxima", (3, 7, 14, 30)),
    ("dias_activos", "constancia", "Siempre presente", "Entra a estudiar {n} días distintos", "calendar", "dias_activos", (5, 15, 40, 90)),
    ("metas", "constancia", "Cumplidor", "Cumple tu meta diaria {n} veces", "clock", "dias_meta", (3, 10, 25, 60)),
    ("minutos", "constancia", "Maratonista", "Acumula {n} minutos de estudio", "zap", "minutos_total", (60, 300, 900, 3000)),
    ("temas_inter", "dominio", "Subiendo", "Llega a nivel Intermedio en {n} temas", "trending", "temas_nivel2", (1, 3, 6, 12)),
    ("temas_avanz", "dominio", "Cima cercana", "Llega a nivel Avanzado en {n} temas", "layers", "temas_nivel3", (1, 3, 6, 10)),
    ("temas_exp", "dominio", "Experto", "Llega a nivel Experto en {n} temas", "award", "temas_nivel4", (1, 2, 4, 8)),
    ("xp", "dominio", "Acumulador de XP", "Gana {n} XP en total", "star", "xp_total", (25, 100, 300, 800)),
    ("ejercicios", "practica", "Practicante", "Resuelve {n} ejercicios prácticos", "bulb", "ejercicios", (1, 5, 15, 40)),
    ("ej_9", "practica", "Matrícula de honor", "Saca 9 o más en {n} ejercicios", "star", "ejercicios_9", (1, 3, 8, 20)),
    ("ej_10", "practica", "Perfección", "Saca 10 en {n} ejercicios", "check", "ejercicios_10", (1, 3, 6, 12)),
    ("respuestas", "examenes", "Incansable", "Responde {n} preguntas de examen", "help", "respuestas", (10, 50, 200, 600)),
    ("aciertos", "examenes", "Buen ojo", "Acierta {n} preguntas", "check", "aciertos", (10, 50, 150, 400)),
    ("expertas", "examenes", "Cerebrito", "Acierta {n} preguntas de dificultad experta", "shield", "aciertos_expertos", (1, 5, 15, 40)),
    ("seguidas", "examenes", "Sin fallar", "Acierta {n} preguntas seguidas", "target", "aciertos_seguidos", (5, 10, 20, 40)),
    ("temas_vistos", "exploracion", "Curioso", "Estudia {n} temas distintos", "book", "temas_explorados", (3, 8, 16, 30)),
    ("materias", "exploracion", "Explorador", "Estudia {n} materias distintas", "layers", "materias_exploradas", (1, 2, 4, 6)),
    ("tutor", "exploracion", "Preguntón", "Hazle {n} preguntas al tutor", "message", "preguntas_tutor", (5, 25, 100, 300)),
    ("clases", "comunidad", "De grupo", "Únete a {n} clases", "users", "clases", (1, 2, 3, 5)),
    ("madrugador", "especiales", "Madrugador", "Estudia antes de las 7:00 en {n} días", "clock", "dias_madrugador", (1, 5, 15, 30)),
    ("noctambulo", "especiales", "Noctámbulo", "Estudia después de las 22:00 en {n} días", "clock", "dias_noctambulo", (1, 5, 15, 30)),
    ("finde", "especiales", "Fin de semana de estudio", "Estudia sábado y domingo en {n} fines de semana", "calendar",
     "fines_de_semana", (1, 3, 8, 16)),
    # ---- Constancia ----
    ("semanas_perfectas", "constancia", "Semana perfecta", "Estudia los 7 días de la semana en {n} semanas", "calendar", "semanas_perfectas", (1, 3, 8, 16)),
    ("semanas_activas", "constancia", "Semana a semana", "Estudia en {n} semanas distintas", "calendar", "semanas_activas", (2, 6, 16, 36)),
    ("meses_activos", "constancia", "Mes a mes", "Estudia en {n} meses distintos", "calendar", "meses_activos", (1, 2, 4, 8)),
    ("mes_intenso", "constancia", "Mes intenso", "Estudia {n} días en un mismo mes", "flame", "mes_intenso", (8, 14, 20, 26)),
    ("dias_30", "constancia", "Sesión larga", "Estudia 30 minutos o más en {n} días", "clock", "dias_30", (3, 10, 25, 60)),
    ("dias_60", "constancia", "Maratón diario", "Estudia 60 minutos o más en {n} días", "zap", "dias_60", (1, 5, 15, 40)),
    ("record_dia", "constancia", "Récord de un día", "Estudia {n} minutos en un solo día", "trending", "record_dia", (30, 60, 120, 240)),
    ("racha_meta", "constancia", "Meta sin falta", "Cumple tu meta diaria {n} días seguidos", "target", "racha_meta", (2, 5, 10, 21)),
    ("semanas_meta", "constancia", "Semana cumplida", "Cumple tu meta en 5 días de {n} semanas", "check", "semanas_meta", (1, 3, 8, 16)),
    ("dias_aciertos", "constancia", "Acertando a diario", "Acierta al menos una pregunta en {n} días", "check", "dias_con_aciertos", (3, 10, 30, 70)),
    ("dias_respuestas", "constancia", "Examinador constante", "Responde preguntas en {n} días distintos", "help", "dias_con_respuestas", (3, 10, 30, 70)),
    ("dias_practica", "constancia", "Práctica diaria", "Resuelve un ejercicio en {n} días distintos", "bulb", "dias_con_ejercicio", (3, 10, 25, 60)),
    # ---- Exámenes ----
    ("calentamiento", "examenes", "Calentamiento", "Acierta {n} preguntas básicas", "check", "aciertos_dif1", (10, 40, 100, 250)),
    ("paso_firme", "examenes", "Paso firme", "Acierta {n} preguntas intermedias", "check", "aciertos_dif2", (10, 40, 100, 250)),
    ("buen_nivel", "examenes", "Buen nivel", "Acierta {n} preguntas avanzadas", "check", "aciertos_dif3", (5, 20, 60, 150)),
    ("dia_productivo", "examenes", "Día productivo", "Responde {n} preguntas en un solo día", "zap", "respuestas_dia", (10, 25, 50, 100)),
    ("dia_acierto", "examenes", "Día de aciertos", "Acierta {n} preguntas en un solo día", "star", "aciertos_dia", (5, 15, 30, 60)),
    ("punteria", "examenes", "Puntería fina", "Mantén {n}% de aciertos (con 20 o más respuestas)", "target", "precision", (60, 75, 85, 95)),
    ("de_errores", "examenes", "De los errores se aprende", "Corrige {n} preguntas que habías fallado", "refresh", "errores_corregidos", (1, 5, 15, 40)),
    ("examinado", "examenes", "Examinado", "Presenta {n} exámenes", "clipboard", "examenes", (1, 5, 15, 40)),
    ("repasador", "examenes", "Repasador", "Haz {n} repasos de errores", "refresh", "repasos", (1, 3, 8, 20)),
    ("examen_perfecto", "examenes", "Examen perfecto", "Saca 100% en {n} exámenes de 5 o más preguntas", "award", "examenes_perfectos", (1, 3, 8, 20)),
    ("examen_aprobado", "examenes", "Examen aprobado", "Saca 70% o más en {n} exámenes de 5 o más preguntas", "check", "examenes_aprobados", (1, 5, 15, 40)),
    ("especialista", "examenes", "Especialista", "Acierta {n} preguntas en una misma materia", "shield", "aciertos_materia", (20, 60, 150, 400)),
    # ---- Práctica ----
    ("aprobador", "practica", "Aprobador", "Saca 6 o más en {n} ejercicios", "check", "ejercicios_aprobados", (3, 10, 25, 60)),
    ("dia_practica", "practica", "Día de práctica", "Resuelve {n} ejercicios en un solo día", "bulb", "ejercicios_dia", (2, 4, 6, 10)),
    ("promedio", "practica", "Promedio de lujo", "Mantén un promedio de {n} en tus ejercicios (con 5 o más)", "star", "promedio_ejercicios", (6, 7, 8, 9)),
    ("practica_variada", "practica", "Práctica variada", "Resuelve ejercicios de {n} temas distintos", "layers", "ejercicios_temas", (1, 3, 6, 12)),
    # ---- Dominio ----
    ("abriendo_temas", "dominio", "Abriendo temas", "Llega a nivel Principiante en {n} temas", "book", "temas_nivel1", (1, 3, 8, 20)),
    ("semana_oro", "dominio", "Semana de oro", "Gana {n} XP en una sola semana", "zap", "xp_semana", (10, 30, 70, 150)),
    ("dia_xp", "dominio", "Día de XP", "Gana {n} XP en un solo día", "zap", "xp_dia", (5, 15, 30, 60)),
    ("leyenda_xp", "dominio", "Leyenda del XP", "Gana {n} XP en total", "star", "xp_total", (150, 500, 1200, 3000)),
    ("titulos", "dominio", "Escalando títulos", "Llega al título número {n} (de 7)", "trending", "titulo_numero", (2, 3, 5, 7)),
    ("multimateria", "dominio", "Multimateria", "Llega a nivel Intermedio en {n} materias", "layers", "materias_nivel2", (1, 2, 4, 6)),
    ("cima_materia", "dominio", "Cima en materia", "Llega a nivel Experto en {n} materias", "award", "materias_experto", (1, 2, 3, 5)),
    # ---- Exploración ----
    ("charla_intensa", "exploracion", "Charla intensa", "Hazle {n} preguntas al tutor en un solo día", "message", "preguntas_dia", (3, 8, 15, 30)),
    ("conversador", "exploracion", "Conversador", "Empieza {n} conversaciones con el tutor", "message", "conversaciones", (1, 5, 20, 60)),
    ("curiosidad", "exploracion", "Curiosidad diaria", "Pregúntale al tutor en {n} días distintos", "search", "dias_tutor", (1, 5, 15, 40)),
    # ---- Comunidad ----
    ("buena_compania", "comunidad", "Buena compañía", "Estudia en una clase con {n} compañeros", "users", "companeros", (3, 6, 12, 25)),
    ("varias_materias", "comunidad", "Clases de varias materias", "Pertenece a clases de {n} materias", "layers", "materias_clases", (1, 2, 3, 4)),
    # ---- Especiales: hábitos de horario y de día de la semana ----
    ("manana", "especiales", "Mañanero", "Estudia entre las 7:00 y las 12:00 en {n} días", "clock", "dias_manana", (5, 20, 50, 100)),
    ("tarde", "especiales", "Tarde productiva", "Estudia entre las 12:00 y las 19:00 en {n} días", "clock", "dias_tarde", (5, 20, 50, 100)),
    ("noche", "especiales", "Noche de estudio", "Estudia entre las 19:00 y las 22:00 en {n} días", "clock", "dias_noche", (5, 20, 50, 100)),
    ("buho", "especiales", "Búho", "Estudia entre las 0:00 y las 5:00 en {n} días", "sparkles", "dias_buho", (1, 3, 8, 20)),
    ("doble_turno", "especiales", "Doble turno", "Estudia en la mañana y en la noche del mismo día, {n} veces", "refresh", "dias_doble_turno", (1, 5, 15, 40)),
    ("lunes", "especiales", "Lunes con ganas", "Estudia {n} lunes", "calendar", "dias_lunes", (1, 4, 12, 26)),
    ("martes", "especiales", "Martes de práctica", "Estudia {n} martes", "calendar", "dias_martes", (1, 4, 12, 26)),
    ("miercoles", "especiales", "Miércoles de mitad", "Estudia {n} miércoles", "calendar", "dias_miercoles", (1, 4, 12, 26)),
    ("jueves", "especiales", "Jueves de repaso", "Estudia {n} jueves", "calendar", "dias_jueves", (1, 4, 12, 26)),
    ("viernes", "especiales", "Viernes sin pereza", "Estudia {n} viernes", "calendar", "dias_viernes", (1, 4, 12, 26)),
    ("sabado", "especiales", "Sábado de estudio", "Estudia {n} sábados", "calendar", "dias_sabado", (1, 4, 12, 26)),
    ("domingo", "especiales", "Domingo de estudio", "Estudia {n} domingos", "calendar", "dias_domingo", (1, 4, 12, 26)),
    ("veterano", "especiales", "Veterano", "Lleva {n} días con tu cuenta", "user", "antiguedad_dias", (7, 30, 90, 180)),
]
POR_ID = {c[0]: c for c in CATALOGO}


# ----------------------------------------------------------------------------------------------------------------
# Meta diaria
# ----------------------------------------------------------------------------------------------------------------
def minutos_por_dia(marcas: list[datetime], zona: tzinfo) -> dict[date, float]:
    """Minutos de uso de cada día (hora local), con la misma regla de pausas que el tiempo total de estudio."""
    por_dia: dict[date, list] = defaultdict(list)
    for m in marcas:
        por_dia[m.astimezone(zona).date()].append(m)
    return {d: actividad.segundos_de_uso(ms) / 60 for d, ms in por_dia.items()}


@memo
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


# ----------------------------------------------------------------------------------------------------------------
# Datos del alumno
# ----------------------------------------------------------------------------------------------------------------
def lunes_de(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def fines_de_semana(dias: set[date]) -> int:
    """Fines de semana en los que se estudió el sábado Y el domingo."""
    return sum(1 for d in dias if d.weekday() == 5 and d + timedelta(days=1) in dias)


def aciertos_seguidos(resultados: list[bool]) -> int:
    """La racha más larga de respuestas correctas seguidas (en el orden en que se contestaron)."""
    mejor = actual = 0
    for ok in resultados:
        actual = actual + 1 if ok else 0
        mejor = max(mejor, actual)
    return mejor


def semanas_y_meses(dias: set[date]) -> dict:
    """Semanas (de lunes a domingo) y meses con actividad; una semana perfecta tiene los 7 días."""
    semanas: dict[date, set] = defaultdict(set)
    meses: dict[tuple, int] = defaultdict(int)
    for d in dias:
        semanas[lunes_de(d)].add(d)
        meses[(d.year, d.month)] += 1
    return {"semanas_activas": len(semanas), "semanas_perfectas": sum(1 for s in semanas.values() if len(s) == 7),
            "meses_activos": len(meses), "mes_intenso": max(meses.values(), default=0)}


def racha_meta(minutos: dict[date, float], meta: int) -> int:
    """La racha más larga de días seguidos cumpliendo la meta diaria."""
    return actividad.racha_maxima({d for d, m in minutos.items() if m >= meta})


def semanas_con_meta(minutos: dict[date, float], meta: int, minimo: int = 5) -> int:
    """Semanas en las que se cumplió la meta diaria al menos `minimo` días."""
    por_semana: dict[date, int] = defaultdict(int)
    for d, m in minutos.items():
        if m >= meta:
            por_semana[lunes_de(d)] += 1
    return sum(1 for n in por_semana.values() if n >= minimo)


def dias_por_nombre(dias: set[date]) -> list[int]:
    """Cuántos lunes, martes... domingos se estudió (posición 0 = lunes)."""
    cuenta = [0] * 7
    for d in dias:
        cuenta[d.weekday()] += 1
    return cuenta


def franjas_horarias(locales: list[datetime]) -> dict[str, int]:
    """Días distintos en que se estudió en cada franja del día (hora local) y días con «doble turno»."""
    horas: dict[date, set] = defaultdict(set)
    for m in locales:
        horas[m.date()].add(m.hour)
    return {"dias_manana": sum(1 for hs in horas.values() if any(7 <= h < 12 for h in hs)),
            "dias_tarde": sum(1 for hs in horas.values() if any(12 <= h < 19 for h in hs)),
            "dias_noche": sum(1 for hs in horas.values() if any(19 <= h < 22 for h in hs)),
            "dias_buho": sum(1 for hs in horas.values() if any(h < 5 for h in hs)),
            "dias_madrugador": sum(1 for hs in horas.values() if any(h < 7 for h in hs)),
            "dias_noctambulo": sum(1 for hs in horas.values() if any(h >= 22 for h in hs)),
            "dias_doble_turno": sum(1 for hs in horas.values() if any(h < 12 for h in hs) and any(h >= 18 for h in hs))}


def maximo_por_dia(fechas: list[date]) -> int:
    """El mayor número de eventos en un mismo día."""
    return max(Counter(fechas).values(), default=0)


def xp_maximos(eventos: list[tuple[date, int]]) -> tuple[int, int]:
    """(mejor día, mejor semana) de XP, a partir de (fecha local, XP)."""
    por_dia: Counter = Counter()
    por_semana: Counter = Counter()
    for d, xp in eventos:
        por_dia[d] += xp
        por_semana[lunes_de(d)] += xp
    return max(por_dia.values(), default=0), max(por_semana.values(), default=0)


def errores_corregidos(respuestas: list[tuple[int, bool]]) -> int:
    """Preguntas que se fallaron y después se contestaron bien (en el orden de las respuestas: (pregunta, acertó))."""
    falladas, corregidas = set(), set()
    for quiz, ok in respuestas:
        if not ok:
            falladas.add(quiz)
        elif quiz in falladas:
            corregidas.add(quiz)
    return len(corregidas)


def examenes_buenos(por_examen: dict[int, list[bool]], minimo_preguntas: int = 5) -> tuple[int, int]:
    """(exámenes perfectos, exámenes con 70% o más) entre los que tienen al menos `minimo_preguntas` respuestas."""
    perfectos = aprobados = 0
    for resultados in por_examen.values():
        if len(resultados) < minimo_preguntas:
            continue
        aciertos = sum(1 for ok in resultados if ok)
        perfectos += aciertos == len(resultados)
        aprobados += aciertos / len(resultados) >= 0.7
    return perfectos, aprobados


def _local(fecha: datetime, zona: tzinfo) -> datetime:
    return (fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)).astimezone(zona)


@memo
def datos_alumno(usuario_id: int, zona: tzinfo, hoy: date | None = None) -> dict:
    """Todo lo necesario para la meta, el calendario y los logros (unas cuantas consultas por tabla)."""
    from core.competencia import nivel_global  # import tardío: competencia usa este módulo

    hoy = hoy or datetime.now(zona).date()
    marcas = actividad.marcas_recientes(usuario_id)
    locales = [m.astimezone(zona) for m in marcas]
    minutos = minutos_por_dia(marcas, zona)
    dias = set(minutos)
    meta = meta_de(usuario_id)
    with get_session() as s:
        respuestas = s.execute(select(RespuestaQuiz.quiz_id, Quiz.tema_id, Quiz.dificultad, RespuestaQuiz.es_correcta,
                                      RespuestaQuiz.fecha, Quiz.conversacion_id)
                               .join(Quiz, Quiz.id == RespuestaQuiz.quiz_id)
                               .where(RespuestaQuiz.alumno_id == usuario_id).order_by(RespuestaQuiz.id)).all()
        intentos = s.execute(select(IntentoEjercicio.tema_id, IntentoEjercicio.puntaje, IntentoEjercicio.fecha)
                             .where(IntentoEjercicio.alumno_id == usuario_id)).all()
        temas = {r[1] for r in respuestas} | {i[0] for i in intentos}
        resp, ejer = niveles._por_tema(s, usuario_id, list(temas)) if temas else ({}, {})
        materia_de = ({t: m for t, m in s.execute(select(Tema.id, Unidad.materia_id).join(Unidad, Unidad.id == Tema.unidad_id)
                                                  .where(Tema.id.in_(temas))).all()} if temas else {})
        conversaciones = s.execute(select(Conversacion.tipo, Conversacion.titulo)
                                   .where(Conversacion.alumno_id == usuario_id)).all()
        preguntas = [_local(f, zona).date() for (f,) in s.execute(
            select(Mensaje.fecha).join(Conversacion, Conversacion.id == Mensaje.conversacion_id)
            .where(Conversacion.alumno_id == usuario_id, Mensaje.rol == "user"))]
        mis_clases = list(s.scalars(select(Inscripcion.clase_id)
                                    .where(Inscripcion.alumno_id == usuario_id, Inscripcion.estado == "activo")))
        companeros = max((n for n in (s.scalar(select(func.count(Inscripcion.id)).where(
            Inscripcion.clase_id == c, Inscripcion.estado == "activo")) - 1 for c in mis_clases)), default=0)
        materias_clases = (set(s.scalars(select(Clase.materia_id).where(Clase.id.in_(mis_clases)))) if mis_clases else set())
        registro = s.scalar(select(Usuario.fecha).where(Usuario.id == usuario_id))

    estados = {t: niveles.calcular_estado(resp.get(t, []), ejer.get(t, [])) for t in temas}
    puntajes = [p for _, p, _ in intentos]
    ok_dias = [_local(r[4], zona).date() for r in respuestas if r[3]]
    resp_dias = [_local(r[4], zona).date() for r in respuestas]
    ejer_dias = [_local(i[2], zona).date() for i in intentos]
    por_examen: dict[int, list[bool]] = defaultdict(list)
    for r in respuestas:
        por_examen[r[5]].append(bool(r[3]))
    perfectos, aprobados = examenes_buenos(por_examen)
    eventos_xp = ([(_local(r[4], zona).date(), niveles.xp_respuesta(r[2], True)) for r in respuestas if r[3]]
                  + [(_local(i[2], zona).date(), niveles.xp_ejercicio(i[1])) for i in intentos])
    xp_dia, xp_semana = xp_maximos(eventos_xp)
    xp_total = sum(e["xp"] for e in estados.values())
    aciertos_por_materia = Counter(materia_de.get(r[1]) for r in respuestas if r[3])
    niveles_por_materia: dict[int, int] = defaultdict(int)
    for t, e in estados.items():
        m = materia_de.get(t)
        niveles_por_materia[m] = max(niveles_por_materia[m], e["nivel"])
    nombres_dias = dias_por_nombre(dias)
    antiguedad = (datetime.now(timezone.utc) - _local(registro, timezone.utc)).days if registro else 0

    datos = {
        "respuestas": len(respuestas), "aciertos": len(ok_dias),
        "aciertos_expertos": sum(1 for r in respuestas if r[3] and r[2] == 4),
        "aciertos_dif1": sum(1 for r in respuestas if r[3] and r[2] == 1),
        "aciertos_dif2": sum(1 for r in respuestas if r[3] and r[2] == 2),
        "aciertos_dif3": sum(1 for r in respuestas if r[3] and r[2] == 3),
        "aciertos_seguidos": aciertos_seguidos([bool(r[3]) for r in respuestas]),
        "errores_corregidos": errores_corregidos([(r[0], bool(r[3])) for r in respuestas]),
        "precision": round(100 * len(ok_dias) / len(respuestas)) if len(respuestas) >= 20 else 0,
        "respuestas_dia": maximo_por_dia(resp_dias), "aciertos_dia": maximo_por_dia(ok_dias),
        "dias_con_respuestas": len(set(resp_dias)), "dias_con_aciertos": len(set(ok_dias)),
        "aciertos_materia": max((n for m, n in aciertos_por_materia.items() if m is not None), default=0),
        "examenes": sum(1 for tipo, _ in conversaciones if tipo == "examen"),
        "repasos": sum(1 for _, titulo in conversaciones if titulo == "Repaso de errores"),
        "examenes_perfectos": perfectos, "examenes_aprobados": aprobados,
        "ejercicios": len(puntajes), "ejercicios_9": sum(1 for p in puntajes if p >= 9),
        "ejercicios_10": sum(1 for p in puntajes if p >= 10), "ejercicios_aprobados": sum(1 for p in puntajes if p >= 6),
        "ejercicios_dia": maximo_por_dia(ejer_dias), "dias_con_ejercicio": len(set(ejer_dias)),
        "ejercicios_temas": len({i[0] for i in intentos}),
        "promedio_ejercicios": int(sum(puntajes) / len(puntajes)) if len(puntajes) >= 5 else 0,
        "mejor_ejercicio": max(puntajes, default=0),
        "temas_nivel1": sum(1 for e in estados.values() if e["nivel"] >= 1),
        "temas_nivel2": sum(1 for e in estados.values() if e["nivel"] >= 2),
        "temas_nivel3": sum(1 for e in estados.values() if e["nivel"] >= 3),
        "temas_nivel4": sum(1 for e in estados.values() if e["nivel"] >= 4),
        "mejor_nivel": max((e["nivel"] for e in estados.values()), default=0),
        "materias_nivel2": sum(1 for m, n in niveles_por_materia.items() if m is not None and n >= 2),
        "materias_experto": sum(1 for m, n in niveles_por_materia.items() if m is not None and n >= 4),
        "xp_total": xp_total, "xp_dia": xp_dia, "xp_semana": xp_semana,
        "titulo_numero": nivel_global(xp_total)["numero"],
        "temas_explorados": len(temas), "materias_exploradas": len(set(materia_de.values())),
        "preguntas_tutor": len(preguntas), "preguntas_dia": maximo_por_dia(preguntas), "dias_tutor": len(set(preguntas)),
        "conversaciones": sum(1 for tipo, _ in conversaciones if tipo in (None, "chat")),
        "clases": len(mis_clases), "companeros": companeros, "materias_clases": len(materias_clases),
        "meta": meta, "hoy": hoy, "minutos": minutos, "minutos_hoy": minutos.get(hoy, 0.0),
        "minutos_total": int(sum(minutos.values())), "dias_activos": len(dias),
        "dias_30": sum(1 for m in minutos.values() if m >= 30), "dias_60": sum(1 for m in minutos.values() if m >= 60),
        "record_dia": int(max(minutos.values(), default=0)),
        "racha": actividad.dias_seguidos(dias, hoy), "racha_maxima": actividad.racha_maxima(dias),
        "dias_meta": dias_meta_cumplida(minutos, meta), "racha_meta": racha_meta(minutos, meta),
        "semanas_meta": semanas_con_meta(minutos, meta), "fines_de_semana": fines_de_semana(dias),
        "antiguedad_dias": antiguedad,
    }
    datos.update(semanas_y_meses(dias))
    datos.update(franjas_horarias(locales))
    for clave, n in zip(("dias_lunes", "dias_martes", "dias_miercoles", "dias_jueves", "dias_viernes", "dias_sabado",
                         "dias_domingo"), nombres_dias):
        datos[clave] = n
    return datos


# ----------------------------------------------------------------------------------------------------------------
# Logros
# ----------------------------------------------------------------------------------------------------------------
def evaluar(datos: dict) -> list[dict]:
    """Cada logro con su nivel actual (0 a 4) y el avance hacia el siguiente."""
    salida = []
    for id_, categoria, titulo, plantilla, icono, clave, umbrales in CATALOGO:
        valor = int(datos.get(clave, 0))
        nivel = sum(1 for u in umbrales if valor >= u)
        siguiente = umbrales[nivel] if nivel < NIVEL_MAXIMO else None
        previo = umbrales[nivel - 1] if nivel else 0
        meta_texto = siguiente if siguiente is not None else umbrales[-1]
        salida.append({
            "id": id_, "categoria": categoria, "titulo": titulo, "icono": icono,
            "tono": CATEGORIAS[categoria][1], "descripcion": plantilla.format(n=meta_texto),
            "umbrales": umbrales, "valor": valor, "nivel": nivel, "nombre_nivel": NOMBRES_NIVEL[nivel],
            "siguiente": siguiente,
            "avance": 100 if siguiente is None else round((valor - previo) / (siguiente - previo) * 100)})
    return salida


def niveles_logrados(usuario_id: int, zona: tzinfo, datos: dict | None = None) -> dict[str, int]:
    return {l["id"]: l["nivel"] for l in evaluar(datos or datos_alumno(usuario_id, zona)) if l["nivel"]}


def resumen(evaluados: list[dict]) -> dict:
    """Totales para el encabezado del perfil: medallas conseguidas, de oro y por categoría."""
    return {"medallas": sum(l["nivel"] for l in evaluados), "maximas": NIVEL_MAXIMO * len(evaluados),
            "oro": sum(1 for l in evaluados if l["nivel"] == NIVEL_MAXIMO),
            "logros": sum(1 for l in evaluados if l["nivel"])}


def revisar_nuevos(usuario_id: int, zona: tzinfo, datos: dict | None = None) -> list[dict]:
    """Avisa con un mensaje emergente los logros (o niveles) conseguidos desde la última revisión de esta sesión.

    La primera revisión de cada sesión solo toma nota (sin avisar), para no repetir logros viejos. Subir a Oro
    además lanza confeti.
    """
    import streamlit as st

    ss = st.session_state
    por_id = {l["id"]: l for l in evaluar(datos or datos_alumno(usuario_id, zona))}
    actuales = {i: l["nivel"] for i, l in por_id.items() if l["nivel"]}
    vistos = ss.get("logros_vistos")
    ss["logros_vistos"] = {i: max(n, (vistos or {}).get(i, 0)) for i, n in actuales.items()}
    if vistos is None:
        return []
    nuevos = [por_id[i] for i, n in sorted(actuales.items()) if n > vistos.get(i, 0)]
    for logro in nuevos:
        st.toast(f"¡Logro desbloqueado: {logro['titulo']} · {logro['nombre_nivel']}!", icon=":material/emoji_events:")
        if logro["nivel"] == NIVEL_MAXIMO:
            ss["confeti"] = True
    return nuevos


# ----------------------------------------------------------------------------------------------------------------
# Vitrina: los logros que el alumno muestra en su perfil
# ----------------------------------------------------------------------------------------------------------------
@memo
def vitrina_de(usuario_id: int) -> list[str]:
    with get_session() as s:
        crudo = s.scalar(select(Usuario.vitrina).where(Usuario.id == usuario_id)) or ""
    return [i for i in crudo.split(",") if i in POR_ID][:MAX_VITRINA]


def guardar_vitrina(usuario_id: int, ids: list[str]) -> tuple[bool, str]:
    limpios = []
    for i in ids:
        if i not in POR_ID:
            return False, "Hay un logro que no existe."
        if i not in limpios:
            limpios.append(i)
    if len(limpios) > MAX_VITRINA:
        return False, f"Puedes mostrar hasta {MAX_VITRINA} logros."
    with get_session() as s:
        u = s.get(Usuario, usuario_id)
        if u is None:
            return False, "La cuenta no existe."
        u.vitrina = ",".join(limpios)
    return True, "Tu vitrina se actualizó."


def elegir_vitrina(evaluados: list[dict], elegidos: list[str]) -> list[dict]:
    """Logros a mostrar: los que el alumno eligió y ya tiene; si no eligió ninguno, sus mejores (por nivel)."""
    por_id = {l["id"]: l for l in evaluados if l["nivel"]}
    propios = [por_id[i] for i in elegidos if i in por_id]
    if propios:
        return propios[:MAX_VITRINA]
    return sorted(por_id.values(), key=lambda l: (-l["nivel"], l["id"]))[:3]


# ----------------------------------------------------------------------------------------------------------------
# Calendario
# ----------------------------------------------------------------------------------------------------------------
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
