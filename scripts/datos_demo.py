"""Crea (o borra) datos de ejemplo para presentar el demo.

Uso, desde la carpeta del proyecto y con el venv activo:
    python scripts/datos_demo.py            # crea los datos
    python scripts/datos_demo.py --borrar   # elimina solo los datos de ejemplo

OJO: escribe en la base de datos de DATABASE_URL (la de Neon si está en el .env),
así que cualquier persona con acceso a esa base verá estos datos.
Todos los usuarios de ejemplo usan el dominio @demo.local.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from core.db import get_session, init_db  # noqa: E402
from core.passwords import hash_password  # noqa: E402
from models.schema import (Actividad, Asignacion, Carrera, Conversacion, Cuatrimestre, Documento, IntentoEjercicio, Materia,  # noqa: E402
                           Mensaje, PreguntaSinRespuesta, Quiz, RespuestaQuiz, Tema, Unidad,
                           Universidad, Usuario)

DOMINIO = "@demo.local"
PASSWORD_DEMO = "demo1234"
UNIVERSIDAD = "Universidad Demo (datos de ejemplo)"
OPCIONES = ["Opción A", "Opción B", "Opción C", "Opción D"]


def borrar() -> None:
    with get_session() as s:
        uids = list(s.scalars(select(Usuario.id).where(Usuario.email.like(f"%{DOMINIO}"))))
        uni = s.scalar(select(Universidad).where(Universidad.nombre == UNIVERSIDAD))
        temas = []
        if uni:
            temas = list(s.scalars(
                select(Tema.id).join(Unidad, Unidad.id == Tema.unidad_id)
                .join(Materia, Materia.id == Unidad.materia_id)
                .join(Cuatrimestre, Cuatrimestre.id == Materia.cuatrimestre_id)
                .join(Carrera, Carrera.id == Cuatrimestre.carrera_id)
                .where(Carrera.universidad_id == uni.id)))
        convs = list(s.scalars(select(Conversacion.id).where(Conversacion.alumno_id.in_(uids)))) if uids else []
        quizzes = list(s.scalars(select(Quiz.id).where(Quiz.conversacion_id.in_(convs)))) if convs else []
        if quizzes:
            s.execute(delete(RespuestaQuiz).where(RespuestaQuiz.quiz_id.in_(quizzes)))
            s.execute(delete(Quiz).where(Quiz.id.in_(quizzes)))
        if convs:
            s.execute(delete(Mensaje).where(Mensaje.conversacion_id.in_(convs)))
            s.execute(delete(Conversacion).where(Conversacion.id.in_(convs)))
        if uids:
            s.execute(delete(IntentoEjercicio).where(IntentoEjercicio.alumno_id.in_(uids)))
            s.execute(delete(Actividad).where(Actividad.usuario_id.in_(uids)))
            s.execute(delete(PreguntaSinRespuesta).where(PreguntaSinRespuesta.alumno_id.in_(uids)))
            s.execute(delete(Asignacion).where(Asignacion.maestro_id.in_(uids)))
            s.execute(delete(Usuario).where(Usuario.id.in_(uids)))
        if temas:
            s.execute(delete(Documento).where(Documento.tema_id.in_(temas)))
            _borrar_indices(temas)
        if uni:
            for modelo, col, ids in _jerarquia(s, uni.id):
                if ids:
                    s.execute(delete(modelo).where(col.in_(ids)))
            s.execute(delete(Universidad).where(Universidad.id == uni.id))
    print("Datos de ejemplo eliminados.")


def _borrar_indices(temas: list[int]) -> None:
    # Elimina de ChromaDB el material indexado de esos temas (si existe).
    try:
        import chromadb
        from core.config import CHROMA_PATH
        cliente = chromadb.PersistentClient(path=CHROMA_PATH)
        for t in temas:
            try:
                cliente.delete_collection(f"tema_{t}")
            except Exception:
                pass
    except Exception as e:
        print("No se pudo limpiar el índice de ChromaDB:", e)


def _jerarquia(s, uni_id: int):
    carreras = list(s.scalars(select(Carrera.id).where(Carrera.universidad_id == uni_id)))
    cuats = list(s.scalars(select(Cuatrimestre.id).where(Cuatrimestre.carrera_id.in_(carreras)))) if carreras else []
    mats = list(s.scalars(select(Materia.id).where(Materia.cuatrimestre_id.in_(cuats)))) if cuats else []
    unis = list(s.scalars(select(Unidad.id).where(Unidad.materia_id.in_(mats)))) if mats else []
    temas = list(s.scalars(select(Tema.id).where(Tema.unidad_id.in_(unis)))) if unis else []
    # orden de borrado: de lo más específico a lo más general
    return [(Tema, Tema.id, temas), (Unidad, Unidad.id, unis), (Materia, Materia.id, mats),
            (Cuatrimestre, Cuatrimestre.id, cuats), (Carrera, Carrera.id, carreras)]


def crear() -> None:
    init_db()
    pw = hash_password(PASSWORD_DEMO)
    ahora = datetime.now(timezone.utc)
    with get_session() as s:
        if s.scalar(select(Usuario.id).where(Usuario.email.like(f"%{DOMINIO}")).limit(1)):
            print("Ya existen datos de ejemplo. Ejecuta primero con --borrar si quieres rehacerlos.")
            return
        uni = Universidad(nombre=UNIVERSIDAD)
        s.add(uni)
        s.flush()
        carrera = Carrera(nombre="Ingeniería (demo)", universidad_id=uni.id)
        s.add(carrera)
        s.flush()
        cuat = Cuatrimestre(nombre="Cuatrimestre 1", carrera_id=carrera.id)
        s.add(cuat)
        s.flush()
        materia = Materia(nombre="Materia de ejemplo", cuatrimestre_id=cuat.id)
        s.add(materia)
        s.flush()
        unidad = Unidad(nombre="Unidad 1", materia_id=materia.id)
        s.add(unidad)
        s.flush()
        tema = Tema(nombre="Tema de ejemplo", unidad_id=unidad.id)
        s.add(tema)
        s.flush()

        maestro = Usuario(nombre="Maestro Demo", email=f"maestro{DOMINIO}", password_hash=pw, rol="maestro")
        s.add(maestro)
        s.flush()
        s.add(Asignacion(maestro_id=maestro.id, materia_id=materia.id))

        # nombre, aciertos de 10, segundos que tarda en responder, segundos entre quizzes
        perfiles = [("Ana Demo", 9, 40, 300), ("Beto Demo", 3, 60, 300), ("Carla Demo", 8, 2, 10)]
        for nombre, aciertos, tarda, entre in perfiles:
            alumno = Usuario(nombre=nombre, email=f"{nombre.split()[0].lower()}{DOMINIO}", password_hash=pw,
                             rol="alumno", cuatrimestre_id=cuat.id)
            s.add(alumno)
            s.flush()
            conv = Conversacion(alumno_id=alumno.id, tema_id=tema.id, titulo="Quiz de ejemplo",
                                fecha=ahora - timedelta(hours=2))
            s.add(conv)
            s.flush()
            inicio = ahora - timedelta(hours=2)
            for i in range(10):
                t = inicio + timedelta(seconds=i * entre)
                quiz = Quiz(conversacion_id=conv.id, tema_id=tema.id, pregunta=f"Pregunta de ejemplo {i + 1}",
                            opciones=OPCIONES, indice_correcto=0, explicacion="Explicación de ejemplo.", fecha=t)
                s.add(quiz)
                s.flush()
                s.add(RespuestaQuiz(quiz_id=quiz.id, alumno_id=alumno.id, es_correcta=i < aciertos,
                                    indice_elegido=0 if i < aciertos else 1,
                                    fecha=t + timedelta(seconds=tarda)))
            for m in range(0, 40, 2):  # marcas de actividad cada 2 min durante 40 min
                s.add(Actividad(usuario_id=alumno.id, fecha=inicio + timedelta(minutes=m)))
            s.add(PreguntaSinRespuesta(alumno_id=alumno.id, tema_id=tema.id,
                                       pregunta=f"¿Pregunta de ejemplo de {nombre.split()[0]} fuera del material?"))
    print("Datos de ejemplo creados.")
    print(f"Usuarios: maestro{DOMINIO}, ana{DOMINIO}, beto{DOMINIO}, carla{DOMINIO}  |  contraseña: {PASSWORD_DEMO}")


if __name__ == "__main__":
    borrar() if "--borrar" in sys.argv else crear()
