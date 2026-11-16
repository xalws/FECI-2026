"""Meta diaria de estudio y logros del alumno.

Todo se calcula con lo que la app ya guarda (actividad, respuestas de quiz, ejercicios, mensajes y clases). Lo único
que se guarda aparte es la meta diaria (`usuarios.meta_diaria_min`) y los logros que el alumno elige mostrar en su
perfil (`usuarios.vitrina`). Los logros no se «guardan»: se evalúan cada vez con reglas puras (`evaluar`), así que
un cambio de reglas se aplica solo.

Cada logro tiene 4 niveles: 1 Bronce, 2 Plata, 3 Élite (con el color de su categoría) y 4 Oro (el más alto).
"""
from collections import defaultdict
from datetime import date, datetime, timedelta, tzinfo

from sqlalchemy import case, func, select

from core import actividad, niveles
from core.db import get_session
from models.schema import (Conversacion, IntentoEjercicio, Inscripcion, Materia, Mensaje, Quiz, RespuestaQuiz, Tema,
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


def datos_alumno(usuario_id: int, zona: tzinfo, hoy: date | None = None) -> dict:
    """Todo lo necesario para la meta, el calendario y los logros (unas cuantas consultas por tabla)."""
    hoy = hoy or datetime.now(zona).date()
    marcas = actividad.marcas_recientes(usuario_id)
    locales = [m.astimezone(zona) for m in marcas]
    minutos = minutos_por_dia(marcas, zona)
    dias = set(minutos)
    meta = meta_de(usuario_id)
    with get_session() as s:
        respuestas = s.execute(select(Quiz.tema_id, Quiz.dificultad, RespuestaQuiz.es_correcta)
                               .join(RespuestaQuiz, RespuestaQuiz.quiz_id == Quiz.id)
                               .where(RespuestaQuiz.alumno_id == usuario_id).order_by(RespuestaQuiz.id)).all()
        intentos = s.execute(select(IntentoEjercicio.tema_id, IntentoEjercicio.puntaje)
                             .where(IntentoEjercicio.alumno_id == usuario_id)).all()
        temas = {r[0] for r in respuestas} | {i[0] for i in intentos}
        resp, ejer = niveles._por_tema(s, usuario_id, list(temas)) if temas else ({}, {})
        materias = (set(s.scalars(select(Unidad.materia_id).join(Tema, Tema.unidad_id == Unidad.id)
                                  .where(Tema.id.in_(temas)))) if temas else set())
        mensajes = s.scalar(select(func.count(Mensaje.id)).join(Conversacion, Conversacion.id == Mensaje.conversacion_id)
                            .where(Conversacion.alumno_id == usuario_id, Mensaje.rol == "user"))
        en_clases = s.scalar(select(func.count(Inscripcion.id))
                             .where(Inscripcion.alumno_id == usuario_id, Inscripcion.estado == "activo"))
    estados = [niveles.calcular_estado(resp.get(t, []), ejer.get(t, [])) for t in temas]
    puntajes = [p for _, p in intentos]
    return {"respuestas": len(respuestas), "aciertos": sum(1 for r in respuestas if r[2]),
            "aciertos_expertos": sum(1 for r in respuestas if r[2] and r[1] == 4),
            "aciertos_seguidos": aciertos_seguidos([bool(r[2]) for r in respuestas]),
            "ejercicios": len(puntajes), "ejercicios_9": sum(1 for p in puntajes if p >= 9),
            "ejercicios_10": sum(1 for p in puntajes if p >= 10),
            "mejor_ejercicio": max(puntajes, default=0),
            "temas_nivel2": sum(1 for e in estados if e["nivel"] >= 2), "temas_nivel3": sum(1 for e in estados if e["nivel"] >= 3),
            "temas_nivel4": sum(1 for e in estados if e["nivel"] >= 4),
            "mejor_nivel": max((e["nivel"] for e in estados), default=0),
            "xp_total": sum(e["xp"] for e in estados),
            "temas_explorados": len(temas), "materias_exploradas": len(materias),
            "preguntas_tutor": int(mensajes or 0), "clases": int(en_clases or 0),
            "meta": meta, "hoy": hoy, "minutos": minutos, "minutos_hoy": minutos.get(hoy, 0.0),
            "minutos_total": int(sum(minutos.values())), "dias_activos": len(dias),
            "racha": actividad.dias_seguidos(dias, hoy), "racha_maxima": actividad.racha_maxima(dias),
            "dias_meta": dias_meta_cumplida(minutos, meta),
            "dias_madrugador": len({m.date() for m in locales if m.hour < 7}),
            "dias_noctambulo": len({m.date() for m in locales if m.hour >= 22}),
            "fines_de_semana": fines_de_semana(dias)}


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
