"""El tutor como guía de la conversación: iniciar la lección, retomarla y dar retroalimentación.

No todo mensaje del alumno es una búsqueda en el material: «comencemos», «continuemos» u «hola» son órdenes
para el tutor, no preguntas sobre el tema.
"""
import re
import unicodedata

from sqlalchemy import select

from core import llm
from core.db import get_session
from models.schema import Tema

SALUDO = ("¡Hola! Soy tu tutor de **{tema}**. ¿Iniciamos la lección o tienes una pregunta?")
SIN_HISTORIAL = "Todavía no hemos visto nada en esta conversación. ¿Iniciamos la lección o tienes una pregunta?"

SYSTEM_INICIAR = """Eres un tutor universitario. El alumno va a empezar a estudiar el tema "{tema}".
Con base ÚNICAMENTE en el CONTEXTO (los OBJETIVOS solo sirven para decidir el orden y qué habilidades practicar),
haz una introducción breve y didáctica en español:
1. De qué trata el tema, en 2 o 3 frases.
2. Los 3 o 4 puntos que vamos a ver.
3. Explica el primer punto con un ejemplo tomado del contexto.
4. Cierra con UNA pregunta corta para comprobar que entendió.
No inventes datos que no estén en el contexto. Usa viñetas y negritas con moderación."""

SYSTEM_CONTINUAR = """Eres un tutor universitario. Estás en medio de una lección sobre "{tema}". Continúa JUSTO donde se
quedó la conversación: no repitas lo ya explicado, avanza al siguiente punto del tema usando ÚNICAMENTE el CONTEXTO,
da un ejemplo del contexto y cierra con UNA pregunta corta de comprobación. Responde en español."""

SYSTEM_RETRO = """Eres un tutor universitario. Da retroalimentación sobre la conversación de estudio del tema "{tema}".
Usa SOLO lo que aparece en la conversación y en el CONTEXTO. Responde en español, en máximo 150 palabras y con
estas tres partes breves: **Lo que ya vimos**, **Dónde tuviste dudas o fallos** (si no hubo, dilo) y
**Qué te recomiendo repasar o practicar ahora**. Termina preguntando si quiere continuar."""

_SALUDOS = {"hola", "holaa", "buenas", "buenos", "dias", "tardes", "noches", "hey", "que", "tal", "saludos", "buen", "dia"}


def _normalizar(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", sin).split())


def detectar_intencion(texto: str) -> str | None:
    # Devuelve "iniciar", "continuar", "retro", "saludo" o None (es una pregunta de contenido).
    t = _normalizar(texto)
    palabras = t.split()
    if not palabras:
        return None
    if len(palabras) <= 8 and re.search(r"retroaliment|que vimos|que hemos visto|lo visto|como voy|como me fue", t):
        return "retro"
    if len(palabras) > 6 or "?" in texto:
        return None
    if any(p.startswith(("comenc", "comenz", "empec", "empez", "inici", "arranc")) for p in palabras):
        return "iniciar"
    if any(p.startswith(("continu", "segui", "sigue", "sigamos", "prosig", "adelante")) for p in palabras):
        return "continuar"
    if all(p in _SALUDOS for p in palabras):
        return "saludo"
    return None


def objetivos_del_tema(tema_id: int) -> str:
    with get_session() as s:
        return s.scalar(select(Tema.objetivos).where(Tema.id == tema_id)) or ""


def _historial_texto(historial: list[dict], ultimos: int = 12) -> str:
    return "\n".join(f"{'Alumno' if m['rol'] == 'user' else 'Tutor'}: {m['contenido'][:600]}"
                     for m in historial[-ultimos:])


def _sistema(plantilla: str, tema: str, nivel: str) -> str:
    extra = llm.AJUSTE_TUTOR.get(nivel, "")
    return plantilla.format(tema=tema) + (f"\n{extra[3:]}" if extra else "")  # sin el «6.» del prompt del chat


def iniciar_leccion(tema: str, objetivos: str, fragmentos: list[dict], nivel: str = "normal",
                    estado_material: str = "sin_material") -> str:
    if not fragmentos:
        que_pasa = ("El material de este tema ya fue cargado, pero su contenido todavía no está disponible para mí. "
                    "Avísale a tu maestro para que lo vuelva a cargar." if estado_material == "sin_indice"
                    else "El maestro todavía no ha subido el contenido de este tema.")
        return (f"Por ahora no puedo dar la lección de **{tema}**. {que_pasa} " +
                (f"Según la retícula, en este tema veremos:\n\n{objetivos}\n\n" if objetivos else "") +
                "Mientras tanto, puedes estudiar otro tema.")
    usuario = (f"OBJETIVOS DEL TEMA:\n{objetivos or '(no hay)'}\n\nCONTEXTO:\n{llm._formatear_contexto(fragmentos)}")
    mensajes = [{"role": "system", "content": _sistema(SYSTEM_INICIAR, tema, nivel)},
                {"role": "user", "content": usuario}]
    return llm._formato_latex(llm._llamar(mensajes, temperature=0.3).strip())


def continuar_leccion(tema: str, historial: list[dict], fragmentos: list[dict], nivel: str = "normal") -> str:
    if not historial:
        return SIN_HISTORIAL
    usuario = (f"CONVERSACIÓN HASTA AHORA:\n{_historial_texto(historial)}\n\n"
               f"CONTEXTO:\n{llm._formatear_contexto(fragmentos) if fragmentos else '(sin material)'}")
    mensajes = [{"role": "system", "content": _sistema(SYSTEM_CONTINUAR, tema, nivel)},
                {"role": "user", "content": usuario}]
    return llm._formato_latex(llm._llamar(mensajes, temperature=0.3).strip())


def retroalimentar(tema: str, historial: list[dict], fragmentos: list[dict]) -> str:
    if not historial:
        return SIN_HISTORIAL
    usuario = (f"CONVERSACIÓN:\n{_historial_texto(historial)}\n\n"
               f"CONTEXTO:\n{llm._formatear_contexto(fragmentos) if fragmentos else '(sin material)'}")
    mensajes = [{"role": "system", "content": SYSTEM_RETRO.format(tema=tema)},
                {"role": "user", "content": usuario}]
    return llm._formato_latex(llm._llamar(mensajes, temperature=0.2).strip())
