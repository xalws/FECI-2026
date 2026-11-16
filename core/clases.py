"""Clases: grupos de alumnos de una materia que crea un maestro.

- Cada clase pertenece a UNA materia y a un maestro (que debe tener esa materia asignada; el administrador puede
  crearlas de cualquiera). Una misma materia puede tener varios grupos.
- El alumno entra con el código de la clase. Si la clase pide aprobación, queda «pendiente» hasta que el maestro
  la apruebe; si no, entra al instante.
- El maestro publica avisos que ven los alumnos de la clase.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from core.cache import memo
from core.db import get_session
from models.schema import Asignacion, Aviso, Clase, Inscripcion, Materia, Tarea, Usuario

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O ni 1/I, para que el código no se confunda al copiarlo
LARGO_CODIGO = 6
MAX_NOMBRE = 120
MAX_AVISO = 500
ACTIVO, PENDIENTE = "activo", "pendiente"


def normalizar_codigo(texto: str) -> str:
    return "".join(c for c in (texto or "").upper() if c.isalnum())


def _codigo_nuevo(s) -> str:
    for _ in range(20):
        codigo = "".join(secrets.choice(ALFABETO) for _ in range(LARGO_CODIGO))
        if not s.scalar(select(Clase.id).where(Clase.codigo == codigo)):
            return codigo
    raise RuntimeError("No se pudo generar un código único para la clase.")


def _puede_gestionar(s, usuario_id: int, clase: Clase | None) -> bool:
    u = s.get(Usuario, usuario_id)
    if clase is None or u is None or not u.activo:
        return False
    return u.rol == "admin" or (u.rol == "maestro" and clase.maestro_id == usuario_id)


# ----------------------------------------------------------------------------------------------------------------
# Maestro
# ----------------------------------------------------------------------------------------------------------------
def materias_para_crear(usuario_id: int) -> dict[int, str]:
    """Materias en las que puede crear clases: las asignadas al maestro, o todas si es administrador."""
    with get_session() as s:
        u = s.get(Usuario, usuario_id)
        if u is None or not u.activo:
            return {}
        q = select(Materia.id, Materia.nombre).order_by(Materia.nombre)
        if u.rol == "maestro":
            q = q.where(Materia.id.in_(select(Asignacion.materia_id).where(Asignacion.maestro_id == usuario_id)))
        elif u.rol != "admin":
            return {}
        return {i: n for i, n in s.execute(q)}


def crear_clase(usuario_id: int, materia_id: int, nombre: str, aprobacion: bool = True) -> tuple[bool, str, int | None]:
    nombre = " ".join((nombre or "").split())
    if not nombre:
        return False, "Escribe un nombre para la clase.", None
    if len(nombre) > MAX_NOMBRE:
        return False, f"El nombre es demasiado largo (máximo {MAX_NOMBRE} caracteres).", None
    if materia_id not in materias_para_crear(usuario_id):
        return False, "Solo puedes crear clases de las materias que tienes asignadas.", None
    with get_session() as s:
        if s.scalar(select(Clase.id).where(Clase.maestro_id == usuario_id, Clase.materia_id == materia_id,
                                           func.lower(Clase.nombre) == nombre.lower())):
            return False, "Ya tienes una clase con ese nombre en esa materia.", None
        c = Clase(nombre=nombre, materia_id=materia_id, maestro_id=usuario_id, codigo=_codigo_nuevo(s),
                  aprobacion=bool(aprobacion))
        s.add(c)
        s.flush()
        return True, f"Clase creada. Comparte el código {c.codigo} con tus alumnos.", c.id


def clases_del_maestro(usuario_id: int) -> list[dict]:
    """Las clases del maestro (todas, si es administrador) con su número de alumnos y de solicitudes."""
    with get_session() as s:
        u = s.get(Usuario, usuario_id)
        if u is None or not u.activo:
            return []
        q = (select(Clase, Materia.nombre, Usuario.nombre).join(Materia, Materia.id == Clase.materia_id)
             .join(Usuario, Usuario.id == Clase.maestro_id).order_by(Clase.activa.desc(), Clase.nombre))
        if u.rol == "maestro":
            q = q.where(Clase.maestro_id == usuario_id)
        elif u.rol != "admin":
            return []
        filas = s.execute(q).all()
        conteos = {}
        for clase_id, estado, n in s.execute(select(Inscripcion.clase_id, Inscripcion.estado, func.count())
                                             .group_by(Inscripcion.clase_id, Inscripcion.estado)):
            conteos.setdefault(clase_id, {})[estado] = n
        return [{"id": c.id, "nombre": c.nombre, "materia_id": c.materia_id, "materia": materia, "maestro": maestro,
                 "maestro_id": c.maestro_id, "codigo": c.codigo, "activa": c.activa, "aprobacion": c.aprobacion,
                 "alumnos": conteos.get(c.id, {}).get(ACTIVO, 0), "pendientes": conteos.get(c.id, {}).get(PENDIENTE, 0)}
                for c, materia, maestro in filas]


def actualizar(usuario_id: int, clase_id: int, nombre: str | None = None, activa: bool | None = None,
               aprobacion: bool | None = None) -> tuple[bool, str]:
    with get_session() as s:
        c = s.get(Clase, clase_id)
        if not _puede_gestionar(s, usuario_id, c):
            return False, "No puedes modificar esta clase."
        if nombre is not None:
            nombre = " ".join(nombre.split())
            if not nombre or len(nombre) > MAX_NOMBRE:
                return False, f"El nombre debe tener entre 1 y {MAX_NOMBRE} caracteres."
            c.nombre = nombre
        if activa is not None:
            c.activa = bool(activa)
        if aprobacion is not None:
            c.aprobacion = bool(aprobacion)
    return True, "Cambios guardados."


def nuevo_codigo(usuario_id: int, clase_id: int) -> tuple[bool, str]:
    """Cambia el código (por ejemplo, si se filtró). Los alumnos que ya están dentro no se afectan."""
    with get_session() as s:
        c = s.get(Clase, clase_id)
        if not _puede_gestionar(s, usuario_id, c):
            return False, "No puedes modificar esta clase."
        c.codigo = _codigo_nuevo(s)
        return True, c.codigo


def eliminar_clase(usuario_id: int, clase_id: int) -> tuple[bool, str]:
    with get_session() as s:
        c = s.get(Clase, clase_id)
        if not _puede_gestionar(s, usuario_id, c):
            return False, "No puedes eliminar esta clase."
        s.execute(delete(Tarea).where(Tarea.clase_id == clase_id))
        s.execute(delete(Aviso).where(Aviso.clase_id == clase_id))
        s.execute(delete(Inscripcion).where(Inscripcion.clase_id == clase_id))
        s.delete(c)
    return True, "Clase eliminada. Los alumnos conservan su progreso."


def alumnos_de_clase(usuario_id: int, clase_id: int, estado: str = ACTIVO) -> list[dict]:
    with get_session() as s:
        if not _puede_gestionar(s, usuario_id, s.get(Clase, clase_id)):
            return []
        q = (select(Inscripcion.id, Usuario.id, Usuario.nombre, Usuario.email, Inscripcion.fecha)
             .join(Usuario, Usuario.id == Inscripcion.alumno_id)
             .where(Inscripcion.clase_id == clase_id, Inscripcion.estado == estado).order_by(Usuario.nombre))
        return [{"inscripcion_id": i, "alumno_id": a, "nombre": n, "email": e, "fecha": f} for i, a, n, e, f in s.execute(q)]


def resolver_solicitud(usuario_id: int, inscripcion_id: int, aprobar: bool) -> tuple[bool, str]:
    with get_session() as s:
        ins = s.get(Inscripcion, inscripcion_id)
        if ins is None or ins.estado != PENDIENTE:
            return False, "La solicitud ya no existe."
        if not _puede_gestionar(s, usuario_id, s.get(Clase, ins.clase_id)):
            return False, "No puedes resolver esta solicitud."
        if aprobar:
            ins.estado = ACTIVO
            return True, "Alumno aceptado en la clase."
        s.delete(ins)
        return True, "Solicitud rechazada."


def quitar_alumno(usuario_id: int, clase_id: int, alumno_id: int) -> tuple[bool, str]:
    with get_session() as s:
        if not _puede_gestionar(s, usuario_id, s.get(Clase, clase_id)):
            return False, "No puedes modificar esta clase."
        r = s.execute(delete(Inscripcion).where(Inscripcion.clase_id == clase_id, Inscripcion.alumno_id == alumno_id))
    return (True, "Alumno quitado de la clase.") if r.rowcount else (False, "El alumno ya no estaba en la clase.")


def alumnos_ids(clase_id: int) -> list[int]:
    """Ids de los alumnos activos de una clase (para filtrar estadísticas; el permiso se revisa en la pantalla)."""
    with get_session() as s:
        return list(s.scalars(select(Inscripcion.alumno_id).where(Inscripcion.clase_id == clase_id,
                                                                  Inscripcion.estado == ACTIVO)))


# ----------------------------------------------------------------------------------------------------------------
# Alumno
# ----------------------------------------------------------------------------------------------------------------
def unirse(alumno_id: int, codigo: str) -> tuple[bool, str]:
    codigo = normalizar_codigo(codigo)
    if len(codigo) != LARGO_CODIGO:
        return False, f"El código tiene {LARGO_CODIGO} letras y números."
    with get_session() as s:
        u = s.get(Usuario, alumno_id)
        if u is None or not u.activo or u.rol != "alumno":
            return False, "Solo los alumnos pueden unirse a una clase."
        c = s.scalar(select(Clase).where(Clase.codigo == codigo))
        if c is None or not c.activa:
            return False, "No encontré una clase activa con ese código. Revísalo con tu maestro."
        ya = s.scalar(select(Inscripcion).where(Inscripcion.clase_id == c.id, Inscripcion.alumno_id == alumno_id))
        if ya is not None:
            return False, ("Ya estás en esta clase." if ya.estado == ACTIVO
                           else "Tu solicitud ya está pendiente: espera a que tu maestro la apruebe.")
        estado = PENDIENTE if c.aprobacion else ACTIVO
        s.add(Inscripcion(clase_id=c.id, alumno_id=alumno_id, estado=estado))
        if estado == PENDIENTE:
            return True, f"Solicitud enviada a «{c.nombre}». Entrarás cuando tu maestro la apruebe."
        return True, f"¡Listo! Ya estás en «{c.nombre}»."


def salir(alumno_id: int, clase_id: int) -> tuple[bool, str]:
    with get_session() as s:
        r = s.execute(delete(Inscripcion).where(Inscripcion.clase_id == clase_id, Inscripcion.alumno_id == alumno_id))
    return (True, "Saliste de la clase.") if r.rowcount else (False, "No estabas en esa clase.")


@memo
def clases_del_alumno(alumno_id: int) -> list[dict]:
    """Clases del alumno (activas y pendientes) con su materia, su maestro y el estado de su inscripción."""
    with get_session() as s:
        q = (select(Clase, Inscripcion.estado, Materia.nombre, Usuario.nombre)
             .join(Inscripcion, Inscripcion.clase_id == Clase.id).join(Materia, Materia.id == Clase.materia_id)
             .join(Usuario, Usuario.id == Clase.maestro_id)
             .where(Inscripcion.alumno_id == alumno_id).order_by(Inscripcion.estado, Clase.nombre))
        return [{"id": c.id, "nombre": c.nombre, "materia_id": c.materia_id, "materia": materia, "maestro": maestro,
                 "estado": estado, "activa": c.activa} for c, estado, materia, maestro in s.execute(q)]


@memo
def materias_del_alumno(alumno_id: int) -> list[int]:
    """Materias de las clases (activas) en las que el alumno ya está aceptado."""
    return sorted({c["materia_id"] for c in clases_del_alumno(alumno_id) if c["estado"] == ACTIVO and c["activa"]})


# ----------------------------------------------------------------------------------------------------------------
# Avisos
# ----------------------------------------------------------------------------------------------------------------
def publicar_aviso(usuario_id: int, clase_id: int, texto: str) -> tuple[bool, str]:
    texto = (texto or "").strip()
    if not texto:
        return False, "Escribe el aviso."
    if len(texto) > MAX_AVISO:
        return False, f"El aviso es demasiado largo (máximo {MAX_AVISO} caracteres)."
    with get_session() as s:
        if not _puede_gestionar(s, usuario_id, s.get(Clase, clase_id)):
            return False, "No puedes publicar en esta clase."
        s.add(Aviso(clase_id=clase_id, autor_id=usuario_id, texto=texto))
    return True, "Aviso publicado."


def borrar_aviso(usuario_id: int, aviso_id: int) -> tuple[bool, str]:
    with get_session() as s:
        a = s.get(Aviso, aviso_id)
        if a is None or not _puede_gestionar(s, usuario_id, s.get(Clase, a.clase_id)):
            return False, "No puedes borrar este aviso."
        s.delete(a)
    return True, "Aviso borrado."


def avisos_de_clase(usuario_id: int, clase_id: int, limite: int = 20) -> list[dict]:
    """Avisos de una clase para quien la administra."""
    with get_session() as s:
        if not _puede_gestionar(s, usuario_id, s.get(Clase, clase_id)):
            return []
        q = select(Aviso).where(Aviso.clase_id == clase_id).order_by(Aviso.fecha.desc(), Aviso.id.desc()).limit(limite)
        return [{"id": a.id, "texto": a.texto, "fecha": a.fecha} for a in s.scalars(q)]


def avisos_para_alumno(alumno_id: int, dias: int = 30, limite: int = 5) -> list[dict]:
    """Avisos recientes de las clases (activas) donde el alumno ya está aceptado; los más nuevos primero."""
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    with get_session() as s:
        q = (select(Aviso, Clase.nombre, Usuario.nombre).join(Clase, Clase.id == Aviso.clase_id)
             .join(Usuario, Usuario.id == Aviso.autor_id)
             .join(Inscripcion, Inscripcion.clase_id == Clase.id)
             .where(Inscripcion.alumno_id == alumno_id, Inscripcion.estado == ACTIVO, Clase.activa.is_(True))
             .order_by(Aviso.fecha.desc(), Aviso.id.desc()))
        salida = []
        for a, clase, autor in s.execute(q):
            f = a.fecha if a.fecha.tzinfo else a.fecha.replace(tzinfo=timezone.utc)  # SQLite la devuelve sin zona
            if f >= desde:
                salida.append({"id": a.id, "texto": a.texto, "fecha": a.fecha, "clase": clase, "autor": autor})
            if len(salida) >= limite:
                break
        return salida
