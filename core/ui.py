"""Selectores en cascada (con buscador): universidad > carrera > cuatrimestre > materia > unidad > tema."""
import streamlit as st
from sqlalchemy import or_, select

from core.db import get_session
from models.schema import Carrera, Cuatrimestre, Materia, Tema, Unidad, Universidad

# (nombre del nivel, tabla, columna que apunta al nivel anterior)
NIVELES = [
    ("universidad", Universidad, None),
    ("carrera", Carrera, "universidad_id"),
    ("cuatrimestre", Cuatrimestre, "carrera_id"),
    ("materia", Materia, "cuatrimestre_id"),
    ("unidad", Unidad, "materia_id"),
    ("tema", Tema, "unidad_id"),
]
ETIQUETAS = {"universidad": "Universidad", "carrera": "Carrera", "cuatrimestre": "Cuatrimestre",
             "materia": "Materia", "unidad": "Unidad", "tema": "Tema"}


def _permitidos(s, materias_ids: list[int]) -> dict[str, set[int]]:
    """Calcula qué universidades/carreras/cuatrimestres contienen las materias permitidas."""
    mats = s.scalars(select(Materia).where(Materia.id.in_(materias_ids))).all()
    cuats = {m.cuatrimestre_id for m in mats}
    cars = {c.carrera_id for c in s.scalars(select(Cuatrimestre).where(Cuatrimestre.id.in_(cuats)))}
    unis = {c.universidad_id for c in s.scalars(select(Carrera).where(Carrera.id.in_(cars)))}
    return {"universidad": unis, "carrera": cars, "cuatrimestre": cuats, "materia": set(materias_ids)}


def _buscar(s, texto: str, hasta: str, materias_permitidas: list[int] | None) -> list[dict]:
    """Busca `texto` en los nombres de toda la jerarquía. Devuelve rutas completas {nivel: (id, nombre)}."""
    niveles = [n for n, _, _ in NIVELES][: [n for n, _, _ in NIVELES].index(hasta) + 1]
    cols = [Universidad, Carrera, Cuatrimestre, Materia, Unidad, Tema][: len(niveles)]
    q = (select(*[c for m in cols for c in (m.id, m.nombre)])
         .select_from(Universidad)
         .join(Carrera, Carrera.universidad_id == Universidad.id)
         .join(Cuatrimestre, Cuatrimestre.carrera_id == Carrera.id)
         .join(Materia, Materia.cuatrimestre_id == Cuatrimestre.id))
    if hasta in ("unidad", "tema"):
        q = q.join(Unidad, Unidad.materia_id == Materia.id)
    if hasta == "tema":
        q = q.join(Tema, Tema.unidad_id == Unidad.id)
    q = q.where(or_(*[m.nombre.icontains(texto, autoescape=True) for m in cols]))
    if materias_permitidas is not None:
        q = q.where(Materia.id.in_(materias_permitidas))
    q = q.order_by(*[m.nombre for m in cols]).limit(50)
    return [{n: (fila[2 * i], fila[2 * i + 1]) for i, n in enumerate(niveles)} for fila in s.execute(q).all()]


def selector_cascada(hasta: str = "tema", materias_permitidas: list[int] | None = None,
                     prefix: str = "sel", buscar: bool | None = None) -> dict[str, int]:
    """Muestra un buscador + selectbox dependientes hasta el nivel `hasta`. Devuelve {nivel: id elegido}.

    - Si escribes en el buscador, lista las rutas completas que coinciden y eliges una directamente.
    - Si un nivel no tiene opciones, se detiene y el diccionario queda incompleto.
    - materias_permitidas: lista de ids para limitar (maestros); None = sin límite.
    - buscar: mostrar buscador (por defecto solo cuando hasta es 'materia', 'unidad' o 'tema').
    """
    if buscar is None:
        buscar = hasta in ("materia", "unidad", "tema")
    resultado: dict[str, int] = {}
    padre_id = None
    with get_session() as s:
        if buscar:
            texto = st.text_input("🔍 Buscar", key=f"{prefix}_buscar", placeholder=
                                  "Escribe parte del nombre de una materia, unidad, tema, carrera…").strip()
            if texto:
                rutas = _buscar(s, texto, hasta, materias_permitidas)
                if not rutas:
                    st.info("Sin resultados. Borra el texto para usar los selectores.")
                    return {}
                etiquetas = {i: " › ".join(r[n][1] for n in r) for i, r in enumerate(rutas)}
                elegido = st.selectbox(f"{len(rutas)} resultado(s)", list(etiquetas), format_func=etiquetas.get,
                                       key=f"{prefix}_res_{hasta}_{texto}")
                return {n: v[0] for n, v in rutas[elegido].items()}
            st.caption("o elige paso a paso:")

        permitidos = _permitidos(s, materias_permitidas) if materias_permitidas is not None else None
        for nombre, modelo, fk in NIVELES:
            q = select(modelo).order_by(modelo.nombre)
            if fk:
                q = q.where(getattr(modelo, fk) == padre_id)
            items = s.scalars(q).all()
            if permitidos is not None and nombre in permitidos:
                items = [i for i in items if i.id in permitidos[nombre]]
            if not items:
                st.info(f"Todavía no hay {ETIQUETAS[nombre].lower()}s disponibles aquí.")
                break
            nombres = {i.id: i.nombre for i in items}
            elegido = st.selectbox(ETIQUETAS[nombre], list(nombres), format_func=nombres.get,
                                   key=f"{prefix}_{nombre}_{padre_id}")
            resultado[nombre] = elegido
            padre_id = elegido
            if nombre == hasta:
                break
    return resultado


def nombre_tema(tema_id: int) -> str:
    with get_session() as s:
        t = s.get(Tema, tema_id)
        return t.nombre if t else ""
