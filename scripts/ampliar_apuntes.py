"""Genera apuntes de estudio para los temas con poco material y los guarda en la base (5 fragmentos por tema).

Cada tema recibe cinco secciones: conceptos clave, procedimiento o reglas, dos ejemplos resueltos y errores comunes con
práctica. Se guardan como el documento «Manual de <materia>.pdf», así el tutor los cita igual que un PDF.

Son apuntes de apoyo escritos por el modelo de lenguaje: lo ideal es que el maestro suba su propio material.

Uso, desde la carpeta del proyecto y con el entorno virtual activo:
    python scripts/ampliar_apuntes.py --lista                      # qué temas tienen poco material
    python scripts/ampliar_apuntes.py --temas 56-60,32-35          # esos temas, en ese orden
    python scripts/ampliar_apuntes.py --materia "Inglés I"         # todos los temas flacos de una materia
    python scripts/ampliar_apuntes.py --temas 61-78 --reemplazar-prueba   # y borra su «Antología» vieja (la primera carga)

Se puede detener y volver a correr: salta los temas que ya tienen apuntes ampliados. Usa la misma clave de Groq que
el tutor; si se agota la cuota diaria se detiene solo para no dejar al tutor sin servicio.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from groq import RateLimitError  # noqa: E402
from llama_index.core import Document  # noqa: E402
from sqlalchemy import delete, func, select  # noqa: E402

from core import llm, rag  # noqa: E402
from core.db import get_session  # noqa: E402
from models.schema import Documento, Fragmento, Materia, Tema, Unidad, Usuario  # noqa: E402

# Nombres de los documentos: «Manual de <materia>.pdf» (los apuntes ampliados) y «Antología de <materia>.pdf» (los de la
# primera carga). Son títulos propios del curso; no se atribuyen a libros ni autores reales.
PATRON_MANUAL = "Manual de %.pdf"
PATRON_ANTOLOGIA = "Antología de %.pdf"
TITULOS = ["Conceptos clave", "Procedimiento o reglas", "Ejemplo resuelto 1", "Ejemplo resuelto 2", "Errores comunes y práctica"]
SISTEMA = """Eres un profesor universitario. Escribes apuntes de estudio claros y CORRECTOS, en español, para estudiantes
de ingeniería de primer cuatrimestre. Responde SOLO con JSON: {"secciones": [{"titulo": "...", "texto": "..."}]} con
EXACTAMENTE estas 5 secciones, en este orden y con estos títulos:
1. "Conceptos clave": 5 o 6 términos del tema, cada uno con su definición en una línea.
2. "Procedimiento o reglas": los pasos numerados, o las reglas y fórmulas esenciales (fórmulas en texto plano, p. ej.
   "V = I x R"; sin markdown ni LaTeX).
3. "Ejemplo resuelto 1": un problema sencillo con datos concretos y su solución paso a paso (si el tema no es numérico,
   un caso o ejemplo de uso completo).
4. "Ejemplo resuelto 2": otro problema de contexto distinto y algo más difícil, resuelto paso a paso.
5. "Errores comunes y práctica": 3 errores típicos de los estudiantes y 2 preguntas de práctica con su respuesta.
Cada "texto" mide entre 450 y 750 caracteres y empieza nombrando el tema. Los cálculos deben ser correctos: revísalos
antes de escribirlos y comprueba que los resultados sean posibles (por ejemplo, en un balance de materia no puede salir
más de un componente del que entra; los porcentajes de una mezcla suman 100 %). No inventes normas, cifras ni datos
que no estés seguro de que son reales. Escribe solo sobre el tema pedido."""


class SinCuotaDiaria(Exception):
    pass


def temas_con_poco_material(minimo: int = 4) -> list[dict]:
    with get_session() as s:
        cuenta = dict(s.execute(select(Fragmento.tema_id, func.count()).group_by(Fragmento.tema_id)).all())
        ampliados = set(s.scalars(select(Documento.tema_id).where(Documento.nombre_archivo.like(PATRON_MANUAL))))
        filas = s.execute(select(Tema.id, Tema.nombre, Tema.objetivos, Unidad.nombre, Materia.nombre)
                          .join(Unidad, Unidad.id == Tema.unidad_id).join(Materia, Materia.id == Unidad.materia_id)
                          .order_by(Materia.id, Unidad.id, Tema.id)).all()
    return [{"id": t, "tema": n, "objetivos": (o or "")[:220], "unidad": u, "materia": m, "fragmentos": cuenta.get(t, 0)}
            for t, n, o, u, m in filas if t not in ampliados and cuenta.get(t, 0) < minimo]


def _llamar(pedido: list[dict], esfuerzo: str) -> str:
    for _ in range(6):
        try:
            # con tope de tokens: si no, Groq reserva el máximo del modelo contra el cupo por minuto
            r = llm._groq().chat.completions.create(**llm._kwargs(pedido, 0.3, True, esfuerzo), max_tokens=4000)
            return r.choices[0].message.content or ""
        except RateLimitError as e:
            if "per day" in str(e) or "TPD" in str(e):
                raise SinCuotaDiaria(str(e)[:200]) from e
            time.sleep(20)
    raise RuntimeError("Groq siguió en su límite por minuto")


def _valido(d: dict) -> bool:
    sec = d.get("secciones")
    return (isinstance(sec, list) and len(sec) == 5
            and all(isinstance(s, dict) and 220 <= len(str(s.get("texto", ""))) <= 1400 for s in sec))


def generar(t: dict, esfuerzo: str) -> list[dict] | None:
    pedido = [{"role": "system", "content": SISTEMA},
              {"role": "user", "content": f"Tema: {t['tema']}\nMateria: {t['materia']}\nUnidad: {t['unidad']}"
                                          + (f"\nObjetivos: {t['objetivos']}" if t["objetivos"] else "")}]
    for _ in range(3):
        try:
            d = json.loads(_llamar(pedido, esfuerzo))
        except SinCuotaDiaria:
            raise
        except Exception:
            time.sleep(5)
            continue
        if _valido(d):
            return [{"titulo": TITULOS[k], "texto": str(s["texto"]).strip()} for k, s in enumerate(d["secciones"])]
    return None


def guardar(t: dict, secciones: list[dict], reemplazar_prueba: bool) -> int:
    archivo = f"Manual de {t['materia']}.pdf"
    with get_session() as s:
        autor = s.scalar(select(Usuario.id).where(Usuario.rol == "admin").order_by(Usuario.id))
        d = Documento(tema_id=t["id"], maestro_id=autor, nombre_archivo=archivo, num_chunks=0)
        s.add(d)
        s.flush()
        doc_id = d.id
    docs = []
    for pagina, sec in enumerate(secciones, 1):
        meta = {"tema_id": t["id"], "documento_id": doc_id, "archivo": archivo, "pagina": pagina}
        docs.append(Document(text=f"{t['tema']} — {sec['titulo']}\n{sec['texto']}", metadata=meta,
                             excluded_embed_metadata_keys=list(meta), excluded_llm_metadata_keys=list(meta)))
    n = rag.indexar(t["id"], docs)
    with get_session() as s:
        s.get(Documento, doc_id).num_chunks = n
        if reemplazar_prueba:  # los apuntes de prueba viejos de este tema dejan de usarse
            viejos = list(s.scalars(select(Documento.id).where(Documento.tema_id == t["id"],
                                                               Documento.nombre_archivo.like(PATRON_ANTOLOGIA))))
            if viejos:
                s.execute(delete(Fragmento).where(Fragmento.documento_id.in_(viejos)))
                s.execute(delete(Documento).where(Documento.id.in_(viejos)))
    return n


def _rangos(texto: str) -> list[int]:
    return [i for r in texto.split(",") for i in range(int(r.split("-")[0]), int(r.split("-")[-1]) + 1)]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--lista", action="store_true", help="solo muestra los temas con poco material")
    p.add_argument("--temas", help="ids de temas, p. ej. 56-60,32-35 (en ese orden)")
    p.add_argument("--materia", action="append", help="nombre exacto de una materia (se puede repetir)")
    p.add_argument("--reemplazar-prueba", action="store_true", help="borra la «Antología» (primera carga) del tema al terminar")
    p.add_argument("--esfuerzo", default="low", choices=["low", "medium"], help="razonamiento del modelo")
    p.add_argument("--pausa", type=float, default=12, help="segundos entre temas (para no saturar el cupo por minuto)")
    a = p.parse_args()

    pendientes = temas_con_poco_material()
    if a.temas:
        orden = _rangos(a.temas)
        pendientes = sorted((t for t in pendientes if t["id"] in orden), key=lambda t: orden.index(t["id"]))
    if a.materia:
        pendientes = [t for t in pendientes if t["materia"] in a.materia]
    if a.lista:
        for t in pendientes:
            print(f"{t['id']:>4}  {t['fragmentos']} frag.  {t['materia']} > {t['tema']}")
        print(f"{len(pendientes)} temas con poco material")
        return
    print(f"Temas por completar: {len(pendientes)}", flush=True)
    hechos = 0
    for t in pendientes:
        try:
            secciones = generar(t, a.esfuerzo)
        except SinCuotaDiaria as e:
            print(f"Se acabó la cuota diaria de Groq; se detiene para no dejar al tutor sin servicio. ({e})", flush=True)
            break
        if not secciones:
            print(f"  ✗ {t['id']} {t['tema']}: el modelo no devolvió apuntes válidos; se omite", flush=True)
            continue
        n = guardar(t, secciones, a.reemplazar_prueba)
        hechos += 1
        print(f"  ✓ {t['id']} {t['materia']} > {t['tema']}: {n} fragmentos", flush=True)
        time.sleep(a.pausa)
    print(f"Terminado: {hechos} temas con apuntes nuevos.", flush=True)


if __name__ == "__main__":
    main()
