"""Tareas con fecha límite: el maestro pide algo a su clase en un tema y cada alumno ve cuánto lleva.

Tres tipos, medidos con la actividad que ya se guarda (no hay que «entregar» nada):
- «preguntas»: responder N preguntas de examen del tema (cuentan las respondidas desde que se asignó la tarea).
- «ejercicios»: resolver N ejercicios prácticos del tema (también desde la asignación).
- «nivel»: llegar a un nivel del tema (1 Principiante a 4 Experto); cuenta el nivel actual del alumno.
El maestro solo puede asignar temas de la materia de la clase, y solo ve a los alumnos de sus clases.
"""
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import delete, func, or_, select

from core import clases, niveles
from core.cache import memo, solo_lectura
from core.clases import ACTIVO, _puede_gestionar
from core.db import get_session
from models.schema import Aviso, Clase, Inscripcion, IntentoEjercicio, Materia, Quiz, RespuestaQuiz, Tarea, Tema, Unidad, Usuario

TIPOS = {"preguntas": "Responder preguntas de examen", "ejercicios": "Resolver ejercicios prácticos",
         "nivel": "Llegar a un nivel del tema"}
LIMITES = {"preguntas": (1, 50, 10), "ejercicios": (1, 10, 2), "nivel": (1, 4, 2)}  # (mínimo, máximo, sugerido)
MAX_INSTRUCCIONES = 300
PRONTO = timedelta(days=2)


def _utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)  # SQLite devuelve las fechas sin zona


def descripcion(tipo: str, meta: int) -> str:
    if tipo == "preguntas":
        return f"Responder {meta} {'pregunta' if meta == 1 else 'preguntas'} de examen"
    if tipo == "ejercicios":
        return f"Resolver {meta} {'ejercicio' if meta == 1 else 'ejercicios'}"
    return f"Llegar al nivel {niveles.NOMBRES.get(meta, meta)}"


def estado_de(avance: int, meta: int, limite: datetime, ahora: datetime) -> str:
    """«hecha», «vencida» (sin cumplir y ya pasó la fecha), «pronto» (vence en 2 días o menos) o «pendiente»."""
    if avance >= meta:
        return "hecha"
    if ahora > _utc(limite):
        return "vencida"
    return "pronto" if _utc(limite) - ahora <= PRONTO else "pendiente"


def texto_plazo(limite: datetime, ahora: datetime, zona) -> str:
    """«vence hoy», «vence mañana», «vence en 5 días» o «venció hace 2 días», según los días del calendario local."""
    dias = (_utc(limite).astimezone(zona).date() - ahora.astimezone(zona).date()).days
    if dias == 0:
        return "vence hoy" if _utc(limite) >= ahora else "venció hoy"
    if dias == 1:
        return "vence mañana"
    if dias > 1:
        return f"vence en {dias} días"
    return "venció ayer" if dias == -1 else f"venció hace {-dias} días"


# ----------------------------------------------------------------------------------------------------------------
# Maestro
# ----------------------------------------------------------------------------------------------------------------
def _texto_aviso(tipo: str, meta: int, tema: str, limite: datetime, zona, instrucciones: str,
                 visible_desde: datetime | None = None) -> str:
    cuando = f" Disponible desde el {_utc(visible_desde).astimezone(zona):%d/%m/%Y}." if visible_desde else ""
    return (f"Nueva tarea: {descripcion(tipo, meta).lower()} en «{tema}». Fecha límite: "
            f"{_utc(limite).astimezone(zona):%d/%m/%Y}." + cuando + (f" {instrucciones}" if instrucciones else ""))[:500]


def _validar(tipo: str, meta, fecha_limite: datetime, instrucciones: str, visible_desde: datetime | None,
             ahora: datetime, limite_original: datetime | None = None) -> str | None:
    """Mensaje de error si los datos de la tarea no son válidos; None si lo son."""
    if tipo not in TIPOS:
        return "Elige qué debe hacer el alumno."
    minimo, maximo, _ = LIMITES[tipo]
    if not isinstance(meta, int) or not minimo <= meta <= maximo:
        return f"La meta debe estar entre {minimo} y {maximo}."
    # al editar se puede dejar la fecha límite como estaba aunque ya haya pasado, pero no moverla a otra fecha pasada
    if _utc(fecha_limite) <= ahora and not (limite_original and _utc(fecha_limite) == _utc(limite_original)):
        return "La fecha límite debe ser futura."
    if visible_desde is not None and _utc(visible_desde) >= _utc(fecha_limite):
        return "La tarea debe publicarse antes de su fecha límite."
    if len((instrucciones or "").strip()) > MAX_INSTRUCCIONES:
        return f"Las indicaciones son demasiado largas (máximo {MAX_INSTRUCCIONES} caracteres)."
    return None


def crear(usuario_id: int, clase_id: int, tema_id: int, tipo: str, meta: int, fecha_limite: datetime,
          instrucciones: str = "", zona=timezone.utc, visible_desde: datetime | None = None) -> tuple[bool, str, int | None]:
    """Asigna una tarea y publica un aviso en la clase (la fecha del aviso va en `zona`).

    Con `visible_desde` en el futuro la tarea queda **programada**: los alumnos la ven, y su aviso aparece, hasta esa fecha.
    """
    ahora = datetime.now(timezone.utc)
    if visible_desde is not None and _utc(visible_desde) <= ahora:
        visible_desde = None  # una fecha pasada o de ahora mismo es publicar de inmediato
    instrucciones = (instrucciones or "").strip()
    error = _validar(tipo, meta, fecha_limite, instrucciones, visible_desde, ahora)
    if error:
        return False, error, None
    with get_session() as s:
        clase = s.get(Clase, clase_id)
        if not _puede_gestionar(s, usuario_id, clase):
            return False, "No puedes asignar tareas en esta clase.", None
        materia_del_tema = s.scalar(select(Unidad.materia_id).join(Tema, Tema.unidad_id == Unidad.id).where(Tema.id == tema_id))
        if materia_del_tema != clase.materia_id:
            return False, "Elige un tema de la materia de la clase.", None
        t = Tarea(clase_id=clase_id, tema_id=tema_id, autor_id=usuario_id, tipo=tipo, meta=meta,
                  instrucciones=instrucciones or None, fecha_limite=_utc(fecha_limite),
                  visible_desde=_utc(visible_desde) if visible_desde else None)
        s.add(t)
        s.flush()
        tema = s.scalar(select(Tema.nombre).where(Tema.id == tema_id))
        s.add(Aviso(clase_id=clase_id, autor_id=usuario_id, tarea_id=t.id,
                    fecha=_utc(visible_desde) if visible_desde else ahora,
                    texto=_texto_aviso(tipo, meta, tema, fecha_limite, zona, instrucciones, visible_desde)))
        mensaje = ("Tarea programada: los alumnos la verán desde la fecha de publicación." if visible_desde
                   else "Tarea asignada y avisada a la clase.")
        return True, mensaje, t.id


def editar(usuario_id: int, tarea_id: int, tema_id: int, tipo: str, meta: int, fecha_limite: datetime,
           instrucciones: str = "", zona=timezone.utc, visible_desde: datetime | None = None) -> tuple[bool, str]:
    """Cambia una tarea: su tema, lo que se pide, la fecha límite, las indicaciones y cuándo se publica.

    Lo que los alumnos ya hicieron se conserva. Su aviso en la clase se actualiza con los datos nuevos.
    """
    ahora = datetime.now(timezone.utc)
    instrucciones = (instrucciones or "").strip()
    with get_session() as s:
        t = s.get(Tarea, tarea_id)
        clase = s.get(Clase, t.clase_id) if t else None
        if t is None or not _puede_gestionar(s, usuario_id, clase):
            return False, "No puedes modificar esta tarea."
        if visible_desde is not None and _utc(visible_desde) <= ahora:
            visible_desde = None
        error = _validar(tipo, meta, fecha_limite, instrucciones, visible_desde, ahora, limite_original=t.fecha_limite)
        if error:
            return False, error
        materia_del_tema = s.scalar(select(Unidad.materia_id).join(Tema, Tema.unidad_id == Unidad.id).where(Tema.id == tema_id))
        if materia_del_tema != clase.materia_id:
            return False, "Elige un tema de la materia de la clase."
        antes = t.visible_desde
        t.tema_id, t.tipo, t.meta = tema_id, tipo, meta
        t.fecha_limite = _utc(fecha_limite)
        t.instrucciones = instrucciones or None
        t.visible_desde = _utc(visible_desde) if visible_desde else None
        if visible_desde is None and antes is not None:
            t.creada = ahora  # se publica ahora: lo que cuenta es lo que hagan desde este momento
        tema = s.scalar(select(Tema.nombre).where(Tema.id == tema_id))
        aviso = s.scalar(select(Aviso).where(Aviso.tarea_id == tarea_id))
        if aviso is not None:
            aviso.texto = _texto_aviso(tipo, meta, tema, fecha_limite, zona, instrucciones, visible_desde)
            if visible_desde is not None:
                aviso.fecha = _utc(visible_desde)
            elif antes is not None:
                aviso.fecha = ahora
    return True, "Tarea actualizada."


def eliminar(usuario_id: int, tarea_id: int) -> tuple[bool, str]:
    with get_session() as s:
        t = s.get(Tarea, tarea_id)
        if t is None or not _puede_gestionar(s, usuario_id, s.get(Clase, t.clase_id)):
            return False, "No puedes borrar esta tarea."
        # su aviso automático también: si no, los alumnos verían el anuncio de una tarea que ya no existe
        s.execute(delete(Aviso).where(Aviso.tarea_id == tarea_id))
        s.delete(t)
    return True, "Tarea borrada."


def _desde(tarea: Tarea) -> datetime:
    """Desde cuándo cuenta lo que hace el alumno: la asignación o, si la tarea se programó, su fecha de publicación."""
    return max(_utc(tarea.creada), _utc(tarea.visible_desde)) if tarea.visible_desde else _utc(tarea.creada)


def _avances(s, tarea: Tarea, alumno_ids: list[int]) -> dict[int, int]:
    """Cuánto lleva cada alumno en la tarea (ya con el tope de la meta no aplicado: el que llama lo ajusta)."""
    if not alumno_ids:
        return {}
    if tarea.tipo == "preguntas":
        q = (select(RespuestaQuiz.alumno_id, func.count()).join(Quiz, Quiz.id == RespuestaQuiz.quiz_id)
             .where(Quiz.tema_id == tarea.tema_id, RespuestaQuiz.alumno_id.in_(alumno_ids),
                    RespuestaQuiz.fecha >= _desde(tarea)).group_by(RespuestaQuiz.alumno_id))
    elif tarea.tipo == "ejercicios":
        q = (select(IntentoEjercicio.alumno_id, func.count())
             .where(IntentoEjercicio.tema_id == tarea.tema_id, IntentoEjercicio.alumno_id.in_(alumno_ids),
                    IntentoEjercicio.fecha >= _desde(tarea)).group_by(IntentoEjercicio.alumno_id))
    else:
        salida = {}
        for aid in alumno_ids:
            resp, ejer = niveles._por_tema(s, aid, [tarea.tema_id])
            salida[aid] = niveles.calcular_estado(resp.get(tarea.tema_id, []), ejer.get(tarea.tema_id, []))["nivel"]
        return salida
    return {aid: n for aid, n in s.execute(q)}


def _tarjeta(t: Tarea, tema: str) -> dict:
    return {"id": t.id, "clase_id": t.clase_id, "tema_id": t.tema_id, "tema": tema, "tipo": t.tipo, "meta": t.meta,
            "descripcion": descripcion(t.tipo, t.meta), "instrucciones": t.instrucciones or "",
            "fecha_limite": _utc(t.fecha_limite), "creada": _utc(t.creada),
            "visible_desde": _utc(t.visible_desde) if t.visible_desde else None}


@solo_lectura
def tareas_de_clase(usuario_id: int, clase_id: int) -> list[dict]:
    """Tareas de la clase con cuántos alumnos ya la cumplieron; las que vencen antes, primero."""
    ahora = datetime.now(timezone.utc)
    with get_session() as s:
        if not _puede_gestionar(s, usuario_id, s.get(Clase, clase_id)):
            return []
        alumnos = list(s.scalars(select(Inscripcion.alumno_id).where(Inscripcion.clase_id == clase_id,
                                                                      Inscripcion.estado == ACTIVO)))
        filas = s.execute(select(Tarea, Tema.nombre).join(Tema, Tema.id == Tarea.tema_id)
                          .where(Tarea.clase_id == clase_id).order_by(Tarea.fecha_limite, Tarea.id)).all()
        salida = []
        for t, tema in filas:
            avances = _avances(s, t, alumnos)
            d = _tarjeta(t, tema)
            d.update({"alumnos": len(alumnos), "hechas": sum(1 for a in alumnos if avances.get(a, 0) >= t.meta),
                      "vencida": ahora > d["fecha_limite"],
                      "programada": bool(d["visible_desde"] and d["visible_desde"] > ahora)})
            salida.append(d)
        return salida


@solo_lectura
def del_maestro(usuario_id: int) -> list[dict]:
    """Todas las tareas de las clases que administra el maestro (todas, si es administrador), con su clase y su cumplimiento."""
    salida = []
    for c in clases.clases_del_maestro(usuario_id):
        for d in tareas_de_clase(usuario_id, c["id"]):
            salida.append({**d, "clase": c["nombre"], "materia": c["materia"], "materia_id": c["materia_id"],
                           "clase_activa": c["activa"]})
    return salida


@solo_lectura
def detalle(usuario_id: int, tarea_id: int) -> list[dict]:
    """Avance de cada alumno de la clase en una tarea (para el maestro)."""
    with get_session() as s:
        t = s.get(Tarea, tarea_id)
        if t is None or not _puede_gestionar(s, usuario_id, s.get(Clase, t.clase_id)):
            return []
        alumnos = s.execute(select(Usuario.id, Usuario.nombre).join(Inscripcion, Inscripcion.alumno_id == Usuario.id)
                            .where(Inscripcion.clase_id == t.clase_id, Inscripcion.estado == ACTIVO)
                            .order_by(Usuario.nombre)).all()
        avances = _avances(s, t, [a for a, _ in alumnos])
        return [{"alumno_id": a, "nombre": n, "avance": min(avances.get(a, 0), t.meta), "meta": t.meta,
                 "hecha": avances.get(a, 0) >= t.meta} for a, n in alumnos]


@solo_lectura
def matriz(usuario_id: int, clase_id: int, zona=timezone.utc) -> pd.DataFrame:
    """Cumplimiento de la clase: una fila por alumno y una columna por tarea («3/10» y una palomita si ya la cumplió)."""
    with get_session() as s:
        if not _puede_gestionar(s, usuario_id, s.get(Clase, clase_id)):
            return pd.DataFrame()
        alumnos = s.execute(select(Usuario.id, Usuario.nombre).join(Inscripcion, Inscripcion.alumno_id == Usuario.id)
                            .where(Inscripcion.clase_id == clase_id, Inscripcion.estado == ACTIVO)
                            .order_by(Usuario.nombre)).all()
        filas = s.execute(select(Tarea, Tema.nombre).join(Tema, Tema.id == Tarea.tema_id)
                          .where(Tarea.clase_id == clase_id).order_by(Tarea.fecha_limite, Tarea.id)).all()
        ids = [a for a, _ in alumnos]
        tabla = {"Alumno": [n for _, n in alumnos]}
        for t, tema in filas:
            avances = _avances(s, t, ids)
            etiqueta = f"{descripcion(t.tipo, t.meta)} · {tema} (hasta {_utc(t.fecha_limite).astimezone(zona):%d/%m})"
            while etiqueta in tabla:  # dos tareas iguales: Excel y pandas no admiten columnas repetidas
                etiqueta += " "
            tabla[etiqueta] = [f"{min(avances.get(a, 0), t.meta)}/{t.meta}" + (" ✓" if avances.get(a, 0) >= t.meta else "")
                               for a in ids]
        return pd.DataFrame(tabla)


# ----------------------------------------------------------------------------------------------------------------
# Alumno
# ----------------------------------------------------------------------------------------------------------------
@memo
def tareas_del_alumno(alumno_id: int) -> list[dict]:
    """Tareas de las clases (activas) donde el alumno ya está aceptado, con su avance y su estado.

    Primero las que faltan, de la fecha más cercana a la más lejana; después las vencidas y al final las hechas.
    """
    ahora = datetime.now(timezone.utc)
    with get_session() as s:
        filas = s.execute(
            select(Tarea, Tema.nombre, Clase.nombre, Materia.nombre)
            .join(Clase, Clase.id == Tarea.clase_id).join(Tema, Tema.id == Tarea.tema_id)
            .join(Materia, Materia.id == Clase.materia_id)
            .join(Inscripcion, Inscripcion.clase_id == Clase.id)
            .where(Inscripcion.alumno_id == alumno_id, Inscripcion.estado == ACTIVO, Clase.activa.is_(True),
                   or_(Tarea.visible_desde.is_(None), Tarea.visible_desde <= ahora))).all()
        salida = []
        for t, tema, clase, materia in filas:
            avance = min(_avances(s, t, [alumno_id]).get(alumno_id, 0), t.meta)
            d = _tarjeta(t, tema)
            d.update({"clase": clase, "materia": materia, "avance": avance,
                      "estado": estado_de(avance, t.meta, t.fecha_limite, ahora)})
            salida.append(d)
    orden = {"pronto": 0, "pendiente": 0, "vencida": 1, "hecha": 2}
    return sorted(salida, key=lambda d: (orden[d["estado"]], d["fecha_limite"], d["id"]))


def pendientes(alumno_id: int) -> list[dict]:
    """Solo las tareas que aún se pueden cumplir (pendientes o por vencer)."""
    return [t for t in tareas_del_alumno(alumno_id) if t["estado"] in ("pendiente", "pronto")]


def por_dia(alumno_id: int, zona) -> dict:
    """{fecha local: [«tarea · tema»]} de las tareas que faltan, para marcarlas en el calendario."""
    salida: dict = {}
    for t in pendientes(alumno_id):
        dia = t["fecha_limite"].astimezone(zona).date()
        salida.setdefault(dia, []).append(f"{t['descripcion']} · {t['tema']}")
    return salida

