from sqlalchemy import select

from core.db import get_session
from models.schema import Carrera, Cuatrimestre, Universidad, Usuario


def _consulta_rutas():
    return (select(Cuatrimestre.id, Universidad.nombre, Carrera.nombre, Cuatrimestre.nombre)
            .select_from(Cuatrimestre)
            .join(Carrera, Carrera.id == Cuatrimestre.carrera_id)
            .join(Universidad, Universidad.id == Carrera.universidad_id))


def cuatrimestre_de(usuario_id: int) -> int | None:
    with get_session() as s:
        return s.scalar(select(Usuario.cuatrimestre_id).where(Usuario.id == usuario_id))


def mapa_academico() -> dict[int, tuple[str, str, str]]:
    with get_session() as s:
        return {i: (u, c, q) for i, u, c, q in s.execute(_consulta_rutas()).all()}


def datos_academicos(cuatrimestre_id: int | None) -> tuple[str, str, str] | None:
    if cuatrimestre_id is None:
        return None
    return mapa_academico().get(cuatrimestre_id)


def asignar_cuatrimestre(usuario_id: int, cuatrimestre_id: int) -> None:
    with get_session() as s:
        u = s.get(Usuario, usuario_id)
        if u is None or u.rol != "alumno":
            raise ValueError("Solo los alumnos tienen universidad y cuatrimestre.")
        if s.get(Cuatrimestre, cuatrimestre_id) is None:
            raise ValueError("Ese cuatrimestre no existe.")
        u.cuatrimestre_id = cuatrimestre_id
