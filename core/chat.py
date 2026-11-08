from sqlalchemy import or_, select

from core.db import get_session
from models.schema import Conversacion, Materia, Mensaje, Tema, Unidad


def crear_conversacion(alumno_id: int, tema_id: int, titulo: str = "") -> int:
    with get_session() as s:
        c = Conversacion(alumno_id=alumno_id, tema_id=tema_id, titulo=titulo[:200])
        s.add(c)
        s.flush()
        return c.id


def guardar_mensaje(conversacion_id: int, rol: str, contenido: str) -> None:
    with get_session() as s:
        s.add(Mensaje(conversacion_id=conversacion_id, rol=rol, contenido=contenido))


def listar_mensajes(conversacion_id: int) -> list[dict]:
    with get_session() as s:
        filas = s.scalars(select(Mensaje).where(Mensaje.conversacion_id == conversacion_id)
                          .order_by(Mensaje.id)).all()
        return [{"rol": m.rol, "contenido": m.contenido} for m in filas]


def listar_conversaciones(alumno_id: int, texto: str = "") -> list[dict]:
    with get_session() as s:
        q = (select(Conversacion, Tema.nombre, Materia.nombre)
             .join(Tema, Tema.id == Conversacion.tema_id)
             .join(Unidad, Unidad.id == Tema.unidad_id)
             .join(Materia, Materia.id == Unidad.materia_id)
             .where(Conversacion.alumno_id == alumno_id)
             .order_by(Conversacion.id.desc()))
        texto = texto.strip()
        if texto:
            en_mensajes = select(Mensaje.conversacion_id).where(Mensaje.contenido.icontains(texto, autoescape=True))
            q = q.where(or_(Conversacion.titulo.icontains(texto, autoescape=True),
                            Tema.nombre.icontains(texto, autoescape=True),
                            Materia.nombre.icontains(texto, autoescape=True),
                            Conversacion.id.in_(en_mensajes)))
        return [{"id": c.id, "fecha": c.fecha, "titulo": c.titulo, "tema": t, "materia": m}
                for c, t, m in s.execute(q).all()]
