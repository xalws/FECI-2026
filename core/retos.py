"""Reto de la semana: una meta corta que cambia cada lunes, igual para todos (así se puede comparar en la liga de la clase).

El reto sale de un calendario fijo (según el número de semana del año), no se guarda en la base: se mide con la
actividad que ya existe (preguntas, ejercicios, días, minutos y XP de la semana, de lunes a domingo). Por eso también se
sabe cuántos retos cumplió el alumno en semanas pasadas, sin ninguna tabla nueva.
"""
from datetime import date, timedelta

# (id, texto con {n}, meta, clave del dato semanal)
RETOS = [
    ("preguntas", "Responde {n} preguntas de examen", 20, "preguntas_semana"),
    ("dias", "Estudia {n} días distintos", 4, "dias_semana"),
    ("ejercicios", "Resuelve {n} ejercicios", 3, "ejercicios_semana"),
    ("xp", "Gana {n} XP", 30, "xp_semana_actual"),
    ("minutos", "Estudia {n} minutos", 120, "minutos_semana"),
]


def lunes_de(dia: date) -> date:
    return dia - timedelta(days=dia.weekday())


def reto_de_semana(hoy: date) -> dict:
    """El reto de la semana de `hoy`: {"id", "texto", "meta", "clave", "lunes", "termina"}."""
    anio, semana, _ = hoy.isocalendar()
    rid, texto, meta, clave = RETOS[(anio * 53 + semana) % len(RETOS)]
    lunes = lunes_de(hoy)
    return {"id": rid, "texto": texto.format(n=meta), "meta": meta, "clave": clave, "lunes": lunes,
            "termina": lunes + timedelta(days=6)}


def dias_para_reiniciar(hoy: date) -> int:
    """Días que faltan para el próximo lunes, cuando empieza otro reto y la liga semanal vuelve a cero."""
    return 7 - hoy.weekday()


def valores_de_semana(lunes: date, resp_dias: list[date], ejer_dias: list[date], minutos: dict[date, float],
                      eventos_xp: list[tuple[date, int]]) -> dict[str, int]:
    """Lo que el alumno hizo en la semana que empieza el `lunes` (las claves de `RETOS`)."""
    fin = lunes + timedelta(days=7)

    def dentro(d: date) -> bool:
        return lunes <= d < fin
    return {"preguntas_semana": sum(1 for d in resp_dias if dentro(d)),
            "ejercicios_semana": sum(1 for d in ejer_dias if dentro(d)),
            "dias_semana": sum(1 for d, m in minutos.items() if dentro(d) and m > 0),
            "minutos_semana": int(sum(m for d, m in minutos.items() if dentro(d))),
            "xp_semana_actual": sum(x for d, x in eventos_xp if dentro(d))}


def avance_semana(datos: dict, hoy: date) -> int:
    """Cuánto lleva el alumno del reto de esta semana (`datos` trae las claves semanales de `datos_alumno`)."""
    return int(datos.get(reto_de_semana(hoy)["clave"], 0))


def retos_cumplidos(resp_dias: list[date], ejer_dias: list[date], minutos: dict[date, float],
                    eventos_xp: list[tuple[date, int]]) -> int:
    """En cuántas semanas (de las que tuvieron actividad) se cumplió el reto que tocaba esa semana."""
    lunes_con_actividad = {lunes_de(d) for d in [*resp_dias, *ejer_dias, *minutos, *(d for d, _ in eventos_xp)]}
    total = 0
    for lunes in lunes_con_actividad:
        reto = reto_de_semana(lunes)
        if valores_de_semana(lunes, resp_dias, ejer_dias, minutos, eventos_xp)[reto["clave"]] >= reto["meta"]:
            total += 1
    return total
