"""Reglas del examen de varias preguntas con dificultad progresiva."""
from core.llm import DIFICULTADES

MIN_DIFICULTAD = 1
MAX_DIFICULTAD = max(DIFICULTADES)
PREGUNTAS_POR_DEFECTO = 5

# Nivel del alumno en el tema (core/progreso.py) -> dificultad con la que empieza el examen
DIFICULTAD_INICIAL = {"apoyo": 1, "normal": 2, "avanzado": 3}


def dificultad_inicial(nivel: str) -> int:
    return DIFICULTAD_INICIAL.get(nivel, 2)


def siguiente_dificultad(actual: int, acerto: bool) -> int:
    # Si acierta, la siguiente pregunta es más difícil; si falla, un poco más fácil.
    nueva = actual + 1 if acerto else actual - 1
    return max(MIN_DIFICULTAD, min(MAX_DIFICULTAD, nueva))


def nuevo_examen(total: int, nivel: str) -> dict:
    return {"total": total, "numero": 1, "dificultad": dificultad_inicial(nivel), "resultados": [], "quiz": None}


def nuevo_repaso(preguntas: list[dict], nivel: str) -> dict:
    # Repaso de errores: no se generan preguntas nuevas, se vuelven a plantear las que el alumno falló.
    ex = nuevo_examen(len(preguntas), nivel)
    ex["tipo"], ex["cola"] = "repaso", list(preguntas)
    return ex


def resumen_repaso(examen: dict) -> str:
    res = examen["resultados"]
    corregidas = sum(1 for r in res if r["acerto"])
    detalle = "\n".join(f"- Pregunta {r['numero']}: {'✅ corregida' if r['acerto'] else '❌ sigue pendiente'}" for r in res)
    cierre = ("¡Excelente, ya dominas esas preguntas!" if corregidas == len(res)
              else "Las que siguen pendientes volverán a aparecer en «Repasar errores».")
    return f"**Repaso terminado: corregiste {corregidas} de {len(res)} errores.**\n\n{detalle}\n\n{cierre}"


def registrar_resultado(examen: dict, acerto: bool) -> dict:
    # Guarda el resultado de la pregunta actual y prepara la siguiente.
    examen["resultados"].append({"numero": examen["numero"], "dificultad": examen["dificultad"], "acerto": acerto})
    examen["dificultad"] = siguiente_dificultad(examen["dificultad"], acerto)
    examen["numero"] += 1
    examen["quiz"] = None
    return examen


def terminado(examen: dict) -> bool:
    return len(examen["resultados"]) >= examen["total"]


def progreso_texto(nivel_antes: int, xp_antes: int, despues: dict) -> str:
    # Lo que ganó el alumno en el tema con este examen (despues = estado de core/niveles.py).
    ganados = max(0, despues["xp_efectivo"] - xp_antes)
    texto = (f"**XP ganados en el tema: +{ganados}.** Nivel actual: **{despues['nivel']} · "
             f"{despues['nombre_nivel']}**.")
    if despues["nivel"] > nivel_antes:
        texto += " 🎉 ¡Subiste de nivel!"
    if despues.get("limitado"):
        texto += " Tu precisión en este tema es baja, así que tu nivel no puede pasar de Principiante hasta mejorarla."
    return texto


def resumen_texto(examen: dict) -> str:
    res = examen["resultados"]
    aciertos = sum(1 for r in res if r["acerto"])
    detalle = "\n".join(f"- Pregunta {r['numero']} ({DIFICULTADES.get(r['dificultad'], '—')}): "
                        f"{'✅' if r['acerto'] else '❌'}" for r in res)
    mas_alta = max((r["dificultad"] for r in res if r["acerto"]), default=None)
    nivel = (f"La dificultad más alta que lograste resolver fue **{DIFICULTADES[mas_alta]}**."
             if mas_alta else "Todavía no resolviste ninguna pregunta; repasa el tema y vuelve a intentarlo.")
    return f"**Examen terminado: {aciertos}/{len(res)} aciertos.**\n\n{detalle}\n\n{nivel}"
