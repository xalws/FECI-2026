"""Retícula de una materia: lectura del PDF del programa de asignatura y creación de unidades y temas."""
import re
import time
import unicodedata

from PyPDF2 import PdfReader
from sqlalchemy import select

from core import llm
from core.db import get_session
from models.schema import Asignacion, Carrera, Cuatrimestre, Materia, Tema, Unidad, Universidad

PAUSA_ENTRE_PARTES = 15  # segundos
PARTE_MAX = 11000 # caracteres por llamada a la IA (el plan gratuito de Groq tiene límite de tokens)
_RUIDO = re.compile(r"^(ELABORÓ|APROBÓ|F-DA-|REVISÓ|VIGENTE).*$", re.M)
_CORTES = ("Proceso Enseñanza", "Proceso de Evaluación")
_CUATRIMESTRE = re.compile(r"Cuatrimestre\s+Créditos\s+Modalidad\s+Horas por semana\s+Horas Totales\s+\w+\s+(\d{1,2})\s+\d")


def paginas_utiles(archivo) -> list[str]:
    # Texto de la portada (asignatura, carrera, cuatrimestre) y de las páginas de unidades y temas, sin ruido.
    lector = PdfReader(archivo)
    if lector.is_encrypted:
        raise ValueError("El PDF está cifrado.")
    paginas, previa_con_temas = [], False
    for i, pagina in enumerate(lector.pages):
        texto = _RUIDO.sub("", pagina.extract_text() or "")
        texto = re.sub(r"[ \t]+", " ", texto)
        texto = re.sub(r"\n\s*\n+", "\n", texto).strip()
        if not texto:
            continue
        for corte in _CORTES:  # lo que viene después no son temas
            if corte in texto:
                texto = texto.split(corte, 1)[0].strip()
        con_temas = "Unidad de Aprendizaje" in texto or bool(re.search(r"\bTemas\b", texto))
        if texto and (i == 0 or con_temas or previa_con_temas):
            paginas.append(texto)
        previa_con_temas = con_temas
    if sum(len(p) for p in paginas) < 100:
        raise ValueError("No se encontró texto en el PDF. Si es un escaneo no será posible leerlo.")
    return paginas


def texto_para_ia(archivo) -> str:
    return "\n\n".join(paginas_utiles(archivo))


def cuatrimestre_del_texto(portada: str) -> str:
    # La tabla de la portada trae el número del cuatrimestre; se lee con una regla fija porque es más fiable
    # que pedírselo a la IA.
    m = _CUATRIMESTRE.search(re.sub(r"\s+", " ", portada))
    return f"Cuatrimestre {int(m.group(1))}" if m else ""


def dividir_en_partes(paginas: list[str], limite: int = PARTE_MAX) -> list[str]:
    # Agrupa unidades completas (nunca parte una a la mitad) en bloques de a lo más `limite` caracteres.
    # Cada bloque lleva la portada para que la IA sepa la asignatura.
    portada, resto = paginas[0], paginas[1:]
    unidades: list[list[str]] = []
    for p in resto:
        if "Unidad de Aprendizaje" in p or not unidades:
            unidades.append([p])
        else:
            unidades[-1].append(p)
    partes, actual, largo = [], [], len(portada)
    for u in unidades:
        tamano = sum(len(p) for p in u)
        if actual and largo + tamano > limite:
            partes.append("\n\n".join([portada] + [p for x in actual for p in x]))
            actual, largo = [], len(portada)
        actual.append(u)
        largo += tamano
    if actual or not partes:
        partes.append("\n\n".join([portada] + [p for x in actual for p in x]))
    return partes


def unir_resultados(resultados: list[dict]) -> dict:
    # Junta las unidades de varios bloques; si una unidad se repite, mezcla sus temas sin duplicar.
    datos = {**resultados[0], "unidades": []}
    por_nombre: dict[str, dict] = {}
    for r in resultados:
        for u in r["unidades"]:
            destino = por_nombre.setdefault(_normalizar(u["nombre"]), {"nombre": u["nombre"], "temas": []})
            vistos = {_normalizar(t["nombre"]) for t in destino["temas"]}
            destino["temas"] += [t for t in u["temas"] if _normalizar(t["nombre"]) not in vistos]
    datos["unidades"] = list(por_nombre.values())
    return datos


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
    # La unidad ayuda a distinguir temas de nombre parecido (p. ej. «Mallas y nodos» en CD y en CA).
    return [{"id": i, "nombre": n, "unidad": u, "descripcion": f"{u}. {n}. {o or ''}".strip()}
            for i, n, o, u in filas]


def estructura(materia_id: int) -> dict:
    # La materia con sus unidades y temas (con ids), para poder editarlos.
    with get_session() as s:
        materia = s.get(Materia, materia_id)
        filas = s.execute(select(Unidad.id, Unidad.nombre, Tema.id, Tema.nombre, Tema.objetivos)
                          .outerjoin(Tema, Tema.unidad_id == Unidad.id)
                          .where(Unidad.materia_id == materia_id).order_by(Unidad.id, Tema.id)).all()
    unidades: dict[int, dict] = {}
    for uid, unombre, tid, tnombre, objetivos in filas:
        u = unidades.setdefault(uid, {"id": uid, "nombre": unombre, "temas": []})
        if tid is not None:
            u["temas"].append({"id": tid, "nombre": tnombre, "objetivos": objetivos or ""})
    return {"id": materia_id, "nombre": materia.nombre if materia else "", "unidades": list(unidades.values())}


def actualizar(materia_id: int, materia: str | None = None, unidades: dict[int, str] | None = None,
               temas: dict[int, dict] | None = None) -> int:
    # Guarda los nombres y objetivos editados. `temas` es {tema_id: {"nombre", "objetivos"}}.
    # Solo cambia lo que de verdad es distinto y devuelve cuántos registros modificó.
    # Los ids deben ser de esta materia; el material y el progreso de los alumnos cuelgan del id, no del nombre.
    cambios = 0
    with get_session() as s:
        m = s.get(Materia, materia_id)
        if m is None:
            raise ValueError("La materia no existe.")
        if materia is not None and materia.strip() != m.nombre:
            if not materia.strip():
                raise ValueError("El nombre de la materia no puede estar vacío.")
            m.nombre, cambios = materia.strip(), cambios + 1
        for uid, nombre in (unidades or {}).items():
            u = s.get(Unidad, uid)
            if u is None or u.materia_id != materia_id:
                raise ValueError("Una unidad no pertenece a esta materia.")
            if not nombre.strip():
                raise ValueError("El nombre de una unidad no puede estar vacío.")
            if nombre.strip() != u.nombre:
                u.nombre, cambios = nombre.strip(), cambios + 1
        for tid, datos in (temas or {}).items():
            t = s.get(Tema, tid)
            if t is None or s.get(Unidad, t.unidad_id).materia_id != materia_id:
                raise ValueError("Un tema no pertenece a esta materia.")
            nombre, objetivos = datos["nombre"].strip(), (datos.get("objetivos") or "").strip()
            if not nombre:
                raise ValueError("El nombre de un tema no puede estar vacío.")
            if nombre != t.nombre or objetivos != (t.objetivos or ""):
                t.nombre, t.objetivos, cambios = nombre, objetivos or None, cambios + 1
    return cambios


def extraer(archivo) -> dict:
    # PDF de retícula -> {"materia", "carrera", "cuatrimestre", "unidades": [{"nombre", "temas": [...]}]}
    paginas = paginas_utiles(archivo)
    partes = dividir_en_partes(paginas)
    resultados = []
    for i, parte in enumerate(partes):
        if i:
            time.sleep(PAUSA_ENTRE_PARTES)  # respeta el límite de tokens por minuto de Groq
        resultados.append(llm.extraer_reticula(parte))
    datos = unir_resultados(resultados)
    cuatrimestre = cuatrimestre_del_texto(paginas[0])
    if cuatrimestre:
        datos["cuatrimestre"] = cuatrimestre
    return datos
