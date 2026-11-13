"""Retícula de una materia: lectura del PDF del programa de asignatura y creación de unidades y temas."""
import re
import unicodedata

from PyPDF2 import PdfReader
from sqlalchemy import select

from core import llm
from core.db import get_session
from models.schema import Asignacion, Carrera, Cuatrimestre, Materia, Tema, Unidad, Universidad

MAX_CARACTERES = 14000  # lo que se manda a la IA (el plan gratuito de Groq tiene límite de tokens)
_RUIDO = re.compile(r"^(ELABORÓ|APROBÓ|F-DA-|REVISÓ|VIGENTE).*$", re.M)
_CORTES = ("Proceso Enseñanza", "Proceso de Evaluación")


def texto_para_ia(archivo) -> str:
    # Devuelve solo lo útil del PDF: portada con la asignatura y las páginas de unidades y temas.
    lector = PdfReader(archivo)
    if lector.is_encrypted:
        raise ValueError("El PDF está cifrado.")
    partes = []
    for i, pagina in enumerate(lector.pages):
        texto = _RUIDO.sub("", pagina.extract_text() or "")
        texto = re.sub(r"[ \t]+", " ", texto)
        texto = re.sub(r"\n\s*\n+", "\n", texto).strip()
        if not texto:
            continue
        for corte in _CORTES:  # lo que viene después no son temas
            if corte in texto:
                texto = texto.split(corte, 1)[0].strip()
        if i == 0 or "Unidad de Aprendizaje" in texto or re.search(r"\bTemas\b", texto) or partes and partes[-1][0]:
            partes.append((("Unidad de Aprendizaje" in texto) or ("Temas" in texto), texto))
    resultado = "\n\n".join(t for _, t in partes if t)
    if len(resultado) < 100:
        raise ValueError("No se encontró texto en el PDF. Si es un escaneo no será posible leerlo.")
    return resultado[:MAX_CARACTERES]


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_acentos.casefold().split())


def _obtener_o_crear(s, modelo, nombre: str, **filtros):
    # Busca por nombre (sin distinguir mayúsculas ni acentos) y, si no existe, lo crea.
    nombre = nombre.strip()
    for fila in s.scalars(select(modelo).filter_by(**filtros)):
        if _normalizar(fila.nombre) == _normalizar(nombre):
            return fila, False
    nueva = modelo(nombre=nombre, **filtros)
    s.add(nueva)
    s.flush()
    return nueva, True


def crear_desde_reticula(datos: dict, universidad: str, carrera: str, cuatrimestre: str,
                         maestro_id: int | None = None) -> dict:
    # Crea (o completa) la materia con sus unidades y temas. Devuelve un resumen de lo creado.
    resumen = {"materia_id": None, "unidades_nuevas": 0, "temas_nuevos": 0, "temas_actualizados": 0}
    with get_session() as s:
        uni, _ = _obtener_o_crear(s, Universidad, universidad)
        car, _ = _obtener_o_crear(s, Carrera, carrera, universidad_id=uni.id)
        cua, _ = _obtener_o_crear(s, Cuatrimestre, cuatrimestre, carrera_id=car.id)
        mat, _ = _obtener_o_crear(s, Materia, datos["materia"], cuatrimestre_id=cua.id)
        resumen["materia_id"] = mat.id
        for u in datos["unidades"]:
            unidad, nueva = _obtener_o_crear(s, Unidad, u["nombre"], materia_id=mat.id)
            resumen["unidades_nuevas"] += int(nueva)
            for t in u["temas"]:
                tema, nuevo = _obtener_o_crear(s, Tema, t["nombre"], unidad_id=unidad.id)
                if nuevo:
                    resumen["temas_nuevos"] += 1
                    tema.objetivos = t.get("objetivos") or None
                elif t.get("objetivos") and tema.objetivos != t["objetivos"]:
                    tema.objetivos = t["objetivos"]
                    resumen["temas_actualizados"] += 1
        if maestro_id is not None and not s.scalar(select(Asignacion.id).where(
                Asignacion.maestro_id == maestro_id, Asignacion.materia_id == mat.id)):
            s.add(Asignacion(maestro_id=maestro_id, materia_id=mat.id))
    return resumen


def temas_de_materia(materia_id: int) -> list[dict]:
    # Temas de la materia en orden, con el texto que los describe (nombre + objetivos).
    with get_session() as s:
        filas = s.execute(select(Tema.id, Tema.nombre, Tema.objetivos, Unidad.nombre)
                          .join(Unidad, Unidad.id == Tema.unidad_id)
                          .where(Unidad.materia_id == materia_id)
                          .order_by(Unidad.id, Tema.id)).all()
    return [{"id": i, "nombre": n, "unidad": u, "descripcion": f"{n}. {o or ''}".strip()} for i, n, o, u in filas]


def extraer(archivo) -> dict:
    # PDF de retícula -> {"materia", "carrera", "cuatrimestre", "unidades": [{"nombre", "temas": [...]}]}
    return llm.extraer_reticula(texto_para_ia(archivo))
