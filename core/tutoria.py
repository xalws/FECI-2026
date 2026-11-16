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
3. Explica SOLO el primer punto, con uno o dos ejemplos tomados del contexto.
4. Cierra con UNA pregunta de comprobación sobre ese primer punto y nada más, parecida a tus ejemplos.
No inventes datos que no estén en el contexto. Usa viñetas y negritas con moderación, sin títulos grandes (#).

""" + llm.REGLA_PREGUNTAS

SYSTEM_CONTINUAR = """Eres un tutor universitario. Estás en medio de una lección sobre "{tema}". Continúa JUSTO donde se
quedó la conversación: no repitas lo ya explicado ni repases todo el contexto, avanza UN solo punto nuevo del tema usando
ÚNICAMENTE el CONTEXTO, con uno o dos ejemplos del contexto, y cierra con UNA pregunta corta de comprobación sobre ese
punto. Si el alumno solo dijo «ok» o algo parecido, simplemente sigue con ese siguiente punto. Responde en español, con
negritas y viñetas pero sin títulos grandes (#).

""" + llm.REGLA_PREGUNTAS

SYSTEM_RETRO = """Eres un tutor universitario. Da retroalimentación sobre la conversación de estudio del tema "{tema}".
Usa SOLO lo que aparece en la conversación y en el CONTEXTO. Responde en español, en máximo 150 palabras y con
estas tres partes breves: **Lo que ya vimos**, **Dónde tuviste dudas o fallos** (si no hubo, dilo) y
**Qué te recomiendo repasar o practicar ahora**. Termina preguntando si quiere continuar."""

SYSTEM_RESUMEN = """Eres un tutor universitario. Haz un resumen de estudio del tema "{tema}" para repasar antes de un examen.
Usa ÚNICAMENTE el CONTEXTO (los OBJETIVOS solo sirven para decidir qué es lo más importante). Responde en español y
con esta estructura breve: **Idea central** (2 o 3 frases), **Conceptos clave** (4 a 6 viñetas con su definición corta),
**Fórmulas o pasos importantes** (solo si aparecen en el contexto) y **Qué suelen confundir** (1 o 2 puntos).
Máximo 250 palabras. No inventes nada que no esté en el contexto."""

_SALUDOS = {"hola", "holaa", "buenas", "buenos", "dias", "tardes", "noches", "hey", "que", "tal", "saludos", "buen", "dia"}


_SIGUIENTE = re.compile(r"^(y )?que sigue( ahora)?$|^(la |el |lo )?(siguiente|proxim[oa])( leccion| tema| punto| paso| parte)?$"
                        r"|^(pasemos a |pasar a |vamos a |ir a )?(la |el )?(siguiente|proxim[oa]) (leccion|tema|punto|paso|parte)$"
                        r"|^avancemos$|^avanza$|^adelante$")


# «pasemos al siguiente tema», «otro tema», «cambiemos de tema»: el alumno quiere dejar este tema (no es una pregunta)
_SIGUIENTE_TEMA = re.compile(r"\b(siguiente|proxim[oa]|otro) tema\b|\bcambi\w* de tema\b")
_PALABRAS_DE_PREGUNTA = {"cual", "cuales", "que", "como", "donde", "cuando", "quien", "por"}


def siguiente_tema(estructura: dict, tema_id: int) -> dict | None:
    """El tema que sigue en la retícula (aunque sea de otra unidad), o None si este es el último o no se encuentra.

    `estructura` es lo que devuelve `reticula.estructura`: {"unidades": [{"id", "nombre", "temas": [{"id", "nombre"}]}]}.
    """
    planos = [(u["id"], u["nombre"], t) for u in estructura["unidades"] for t in u["temas"]]
    for i, (unidad_id, _unidad, tema) in enumerate(planos):
        if tema["id"] == tema_id:
            if i + 1 >= len(planos):
                return None
            sig_unidad_id, sig_unidad, sig = planos[i + 1]
            return {"tema_id": sig["id"], "nombre": sig["nombre"], "unidad_id": sig_unidad_id, "unidad": sig_unidad,
                    "cambia_unidad": sig_unidad_id != unidad_id}
    return None


_RESUMEN = re.compile(r"^(dame |hazme |quiero |necesito )?(el |un )?resumen( general| del tema| del contenido)?$"
                      r"|^resume(me)?( el)?( tema)?$")


def resumir_tema(tema: str, objetivos: str, fragmentos: list[dict], nivel: str = "normal") -> str:
    if not fragmentos:
        return "Todavía no hay material de este tema para resumir. Cuando tu maestro lo suba, podré hacerte el resumen."
    usuario = f"OBJETIVOS DEL TEMA:\n{objetivos or '(no hay)'}\n\nCONTEXTO:\n{llm._formatear_contexto(fragmentos)}"
    mensajes = [{"role": "system", "content": _sistema(SYSTEM_RESUMEN, tema, nivel)},
                {"role": "user", "content": usuario}]
    return llm._formato_latex(llm._llamar(mensajes, temperature=0.2).strip())


def consulta_de_busqueda(historial: list[dict], pregunta: str) -> str:
    """Texto con el que se busca en el material.

    Un mensaje corto («como?», «y eso?») no dice nada por sí solo: se le suma lo último que explicó el tutor y lo
    último que preguntó el alumno, para que la búsqueda encuentre el pasaje del que se está hablando.
    """
    if len(pregunta.split()) >= 6:
        return pregunta
    tutor = [m["contenido"] for m in historial if m["rol"] != "user"]
    alumno = [m["contenido"] for m in historial if m["rol"] == "user"]
    partes = [pregunta]
    if tutor:
        partes.append(tutor[-1][:400])
    if alumno:
        partes.append(alumno[-1])
    return " ".join(partes)


def es_seguimiento(historial: list[dict], pregunta: str) -> bool:
    """True si es un mensaje corto que depende de lo ya conversado (aunque la búsqueda no halle nada por sí sola)."""
    return bool(historial) and len(pregunta.split()) < 6


def _normalizar(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", sin).split())


def detectar_intencion(texto: str) -> str | None:
    # Devuelve "iniciar", "continuar", "retro", "resumen", "siguiente_tema", "saludo" o None (es una pregunta de contenido).
    t = _normalizar(texto)
    palabras = t.split()
    if not palabras:
        return None
    if len(palabras) <= 8 and re.search(r"retroaliment|que vimos|que hemos visto|lo visto|como voy|como me fue", t):
        return "retro"
    if len(palabras) <= 8 and _SIGUIENTE_TEMA.search(t) and not set(palabras) & _PALABRAS_DE_PREGUNTA:
        return "siguiente_tema"  # «pasemos al siguiente tema»: se cambia de tema en el menú, no se sigue esta lección
    if len(palabras) <= 6 and _SIGUIENTE.search(t):
        return "continuar"  # «siguiente lección», «¿qué sigue?», «avancemos»
    if len(palabras) <= 5 and _RESUMEN.search(t):
        return "resumen"  # «resumen del tema» (un resumen de algo concreto es una pregunta de contenido)
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
