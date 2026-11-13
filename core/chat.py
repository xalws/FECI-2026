from sqlalchemy import func, or_, select

from core.db import get_session
from models.schema import Conversacion, Materia, Mensaje, PreguntaSinRespuesta, Tema, Unidad

# Títulos que usaban los ejercicios y exámenes antes de que existiera la columna «tipo»
TITULOS_ANTIGUOS_NO_CHAT = ("Examen", "Ejercicio práctico", "Quiz")


def crear_conversacion(alumno_id: int, tema_id: int, titulo: str = "", tipo: str = "chat") -> int:
    with get_session() as s:
        c = Conversacion(alumno_id=alumno_id, tema_id=tema_id, titulo=titulo[:200], tipo=tipo)
        s.add(c)
        s.flush()
        return c.id


def guardar_mensaje(conversacion_id: int, rol: str, contenido: str) -> None:
    with get_session() as s:
        s.add(Mensaje(conversacion_id=conversacion_id, rol=rol, contenido=contenido))


def registrar_sin_respuesta(alumno_id: int, tema_id: int, pregunta: str) -> None:
    # Guarda la pregunta para que el maestro vea qué material falta subir.
    try:
        with get_session() as s:
            s.add(PreguntaSinRespuesta(alumno_id=alumno_id, tema_id=tema_id, pregunta=pregunta[:1000]))
    except Exception:
        pass  # no debe romper el chat


def listar_mensajes(conversacion_id: int) -> list[dict]:
    with get_session() as s:
        filas = s.scalars(select(Mensaje).where(Mensaje.conversacion_id == conversacion_id)
                          .order_by(Mensaje.id)).all()
        return [{"rol": m.rol, "contenido": m.contenido} for m in filas]


def conversaciones_del_tema(alumno_id: int, tema_id: int, limite: int = 20) -> list[dict]:
    # Conversaciones de chat (no ejercicios ni exámenes) del alumno en un tema que ya tienen mensajes.
    with get_session() as s:
        con_mensajes = select(Mensaje.conversacion_id).group_by(Mensaje.conversacion_id)
        q = (select(Conversacion, func.count(Mensaje.id))
             .join(Mensaje, Mensaje.conversacion_id == Conversacion.id)
             .where(Conversacion.alumno_id == alumno_id, Conversacion.tema_id == tema_id,
                    or_(Conversacion.tipo.is_(None), Conversacion.tipo == "chat"),
                    Conversacion.titulo.notin_(TITULOS_ANTIGUOS_NO_CHAT),
                    Conversacion.id.in_(con_mensajes))
             .group_by(Conversacion.id).order_by(Conversacion.id.desc()).limit(limite))
        return [{"id": c.id, "fecha": c.fecha, "titulo": c.titulo, "mensajes": n} for c, n in s.execute(q).all()]


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
