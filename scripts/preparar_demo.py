"""Prepara (o borra) una demostración lista para presentar: maestro, administrador, cuatro alumnos y una clase de Metrología
con dos semanas de actividad, tareas y avisos, para que el boletín, las estadísticas y el repaso tengan qué mostrar.

Uso, desde la carpeta del proyecto y con el entorno virtual activo:
    python scripts/preparar_demo.py            # crea (o rehace) la demostración
    python scripts/preparar_demo.py --borrar   # elimina solo lo que creó este script

Todas las cuentas usan el dominio @feci.local y la contraseña `PASSWORD_DEMO` (es de demostración: no uses una real).
OJO: escribe en la base de DATABASE_URL (la de Neon si está en el .env); quien tenga acceso a esa base verá estos datos.
No toca las cuentas @demo.local ni el resto de la base.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from core import tareas  # noqa: E402
from core.db import get_session, init_db  # noqa: E402
from core.passwords import hash_password  # noqa: E402
from models.schema import (Actividad, Asignacion, Aviso, Clase, Conversacion, Inscripcion, IntentoEjercicio, Materia,  # noqa: E402
                           Mensaje, PreguntaSinRespuesta, Quiz, RespuestaQuiz, Sesion, Tarea, Tarjeta, Tema, Unidad, Usuario)

DOMINIO = "@feci.local"
PASSWORD_DEMO = "Demo-FECI-2026"
CODIGO_CLASE = "FECI26"
NOMBRE_CLASE = "Metrología · Grupo FECI"
MATERIAS = ("Metrología", "Circuitos Eléctricos")  # las que se le asignan al maestro de la demostración
ahora = datetime.now(timezone.utc)

CUENTAS = {
    "maestro": ("Laura Mendoza (maestra)", f"maestro{DOMINIO}", "maestro"),
    "admin": ("Administración FECI", f"admin{DOMINIO}", "admin"),
    "ana": ("Ana Ramírez", f"ana{DOMINIO}", "alumno"),
    "luis": ("Luis Hernández", f"luis{DOMINIO}", "alumno"),
    "sofia": ("Sofía Torres", f"sofia{DOMINIO}", "alumno"),
    "diego": ("Diego Ruiz", f"diego{DOMINIO}", "alumno"),
}

# (tema, pregunta, opciones con la correcta primero, explicación)
BANCO = [
    ("Introducción a la Metrología", "¿Qué estudia la metrología?",
     ["La ciencia de la medición y sus aplicaciones", "El clima de una región", "La resistencia de los materiales", "Las propiedades de los metales"],
     "La metrología es la ciencia de la medición y sus aplicaciones."),
    ("Introducción a la Metrología", "¿Cuál es la unidad base de longitud en el Sistema Internacional?",
     ["El metro", "El pie", "El kilómetro", "La pulgada"], "En el SI la unidad base de longitud es el metro (m)."),
    ("Introducción a la Metrología", "¿Qué es la trazabilidad de una medición?",
     ["Poder relacionarla con patrones nacionales o internacionales mediante calibraciones documentadas",
      "La rapidez con que se obtiene", "El color del instrumento usado", "El costo del instrumento"],
     "La trazabilidad une la medición con un patrón de referencia por una cadena ininterrumpida de calibraciones."),
    ("Conversión entre Sistemas de Unidades de Medida", "¿Cuántos milímetros hay en 2.5 cm?",
     ["25 mm", "2.5 mm", "250 mm", "0.25 mm"], "1 cm = 10 mm, así que 2.5 cm = 25 mm."),
    ("Conversión entre Sistemas de Unidades de Medida", "Una pulgada equivale exactamente a:",
     ["25.4 mm", "2.54 mm", "254 mm", "10 mm"], "Por definición, 1 in = 25.4 mm."),
    ("Conversión entre Sistemas de Unidades de Medida", "¿Cuántos metros son 3 500 mm?",
     ["3.5 m", "35 m", "0.35 m", "350 m"], "1 m = 1 000 mm, así que 3 500 mm = 3.5 m."),
    ("Clasificación de Instrumentos para mediciones geométricas",
     "¿Qué instrumento mide diámetros exteriores con una resolución típica de 0.01 mm?",
     ["El micrómetro", "La regla graduada", "La cinta métrica", "El nivel de burbuja"],
     "El micrómetro de exteriores suele resolver 0.01 mm; la regla y la cinta, solo 1 mm."),
    ("Clasificación de Instrumentos para mediciones geométricas", "El calibrador vernier sirve para medir:",
     ["Exteriores, interiores y profundidades", "Solo temperatura", "Solo masa", "Solo corriente eléctrica"],
     "El vernier tiene mordazas para exteriores e interiores y una varilla para profundidades."),
    ("Técnicas de medición dimensional", "Una medición directa es aquella en la que:",
     ["El valor se lee directamente del instrumento", "Se calcula a partir de otras mediciones",
      "Se estima a simple vista", "Se repite cien veces"], "En la medición directa el instrumento da el valor buscado."),
    ("Tolerancia y dimensionamiento geométrico", "Una pieza de 20 mm con tolerancia de ±0.05 mm es aceptable si mide:",
     ["Entre 19.95 mm y 20.05 mm", "Entre 19.5 mm y 20.5 mm", "Entre 20.00 mm y 20.05 mm", "Entre 19.05 mm y 20.95 mm"],
     "±0.05 mm significa 0.05 mm por debajo y por arriba de 20 mm."),
]

# Perfil de cada alumno: (preguntas de quiz con su acierto, días de la semana con actividad, minutos por sesión)
# `semana_actual` y `semana_previa`: lista de (días atrás, ¿acierta?) por cada respuesta
PERFILES = {
    "ana": {"actual": [(0, 1), (1, 1), (1, 1), (2, 1), (2, 0), (3, 1), (4, 1), (4, 1), (5, 1), (6, 1), (6, 1), (6, 1)],
            "previa": [(8, 1), (9, 0), (10, 1), (12, 1)], "dias": [0, 1, 2, 3, 4, 5, 6], "mensajes": 6},
    "luis": {"actual": [(1, 0), (1, 0), (2, 0), (2, 1), (3, 0), (4, 0), (4, 0), (5, 1)],
             "previa": [(9, 1), (10, 0), (11, 1)], "dias": [1, 2, 3, 4, 5], "mensajes": 4},
    "sofia": {"actual": [(0, 1), (1, 1), (2, 0), (3, 1), (5, 1), (6, 0)],
              "previa": [(8, 1), (9, 1), (11, 0), (13, 1)], "dias": [0, 1, 3, 5, 6], "mensajes": 3},
    "diego": {"actual": [], "previa": [(9, 1), (10, 1), (12, 0)], "dias": [], "dias_previos": [9, 10, 12], "mensajes": 0},
}


def borrar() -> None:
    with get_session() as s:
        uids = list(s.scalars(select(Usuario.id).where(Usuario.email.like(f"%{DOMINIO}"))))
        clases = list(s.scalars(select(Clase.id).where(Clase.maestro_id.in_(uids)))) if uids else []
        if clases:
            s.execute(delete(Tarea).where(Tarea.clase_id.in_(clases)))
            s.execute(delete(Aviso).where(Aviso.clase_id.in_(clases)))
            s.execute(delete(Inscripcion).where(Inscripcion.clase_id.in_(clases)))
            s.execute(delete(Clase).where(Clase.id.in_(clases)))
        for uid in uids:
            s.execute(delete(Inscripcion).where(Inscripcion.alumno_id == uid))
            s.execute(delete(Tarjeta).where(Tarjeta.alumno_id == uid))
            s.execute(delete(Tarea).where(Tarea.autor_id == uid))
            s.execute(delete(Aviso).where(Aviso.autor_id == uid))
            convs = list(s.scalars(select(Conversacion.id).where(Conversacion.alumno_id == uid)))
            quizzes = list(s.scalars(select(Quiz.id).where(Quiz.conversacion_id.in_(convs)))) if convs else []
            if quizzes:
                s.execute(delete(Tarjeta).where(Tarjeta.quiz_id.in_(quizzes)))
                s.execute(delete(RespuestaQuiz).where(RespuestaQuiz.quiz_id.in_(quizzes)))
                s.execute(delete(Quiz).where(Quiz.id.in_(quizzes)))
            if convs:
                s.execute(delete(Mensaje).where(Mensaje.conversacion_id.in_(convs)))
                s.execute(delete(Conversacion).where(Conversacion.id.in_(convs)))
            for modelo, col in ((Actividad, Actividad.usuario_id), (IntentoEjercicio, IntentoEjercicio.alumno_id),
                                (PreguntaSinRespuesta, PreguntaSinRespuesta.alumno_id), (Sesion, Sesion.usuario_id),
                                (RespuestaQuiz, RespuestaQuiz.alumno_id), (Asignacion, Asignacion.maestro_id)):
                s.execute(delete(modelo).where(col == uid))
            s.execute(delete(Usuario).where(Usuario.id == uid))
    print("Demostración eliminada.")


def crear() -> None:
    init_db()
    borrar()
    with get_session() as s:
        materia = {m.nombre: m for m in s.scalars(select(Materia).where(Materia.nombre.in_(MATERIAS)))}
        if "Metrología" not in materia:
            raise SystemExit("No existe la materia Metrología en la base: carga primero la retícula.")
        mat = materia["Metrología"]
        temas = {t.nombre: t.id for t in s.scalars(select(Tema).join(Unidad, Unidad.id == Tema.unidad_id)
                                                   .where(Unidad.materia_id == mat.id))}
        faltan = {b[0] for b in BANCO} - set(temas)
        if faltan:
            raise SystemExit(f"Faltan temas de Metrología en la base: {sorted(faltan)}")
        ids = {}
        for clave, (nombre, email, rol) in CUENTAS.items():
            u = Usuario(nombre=nombre, email=email, rol=rol, password_hash=hash_password(PASSWORD_DEMO),
                        cuatrimestre_id=mat.cuatrimestre_id if rol == "alumno" else None)
            s.add(u)
            s.flush()
            ids[clave] = u.id
        for m in materia.values():
            s.add(Asignacion(maestro_id=ids["maestro"], materia_id=m.id))
        clase = Clase(nombre=NOMBRE_CLASE, materia_id=mat.id, maestro_id=ids["maestro"], codigo=CODIGO_CLASE, aprobacion=False)
        s.add(clase)
        s.flush()
        for clave in ("ana", "luis", "sofia", "diego"):
            s.add(Inscripcion(clase_id=clase.id, alumno_id=ids[clave], estado="activo"))

        for clave, perfil in PERFILES.items():
            uid = ids[clave]
            conv = Conversacion(alumno_id=uid, tema_id=temas[BANCO[0][0]], titulo="Examen", tipo="examen",
                                fecha=ahora - timedelta(days=7))
            s.add(conv)
            s.flush()
            for n, (dias, acierta) in enumerate(perfil["actual"] + perfil["previa"]):
                tema, pregunta, opciones, explicacion = BANCO[(n * 3 + len(clave)) % len(BANCO)]
                giro = n % 4  # que la correcta no sea siempre la primera opción
                mostradas = opciones[giro:] + opciones[:giro]
                correcta = mostradas.index(opciones[0])
                q = Quiz(conversacion_id=conv.id, tema_id=temas[tema], pregunta=pregunta, opciones=mostradas,
                         indice_correcto=correcta, explicacion=explicacion, dificultad=2,
                         fecha=ahora - timedelta(days=dias, hours=3))
                s.add(q)
                s.flush()
                elegido = correcta if acierta else (correcta + 1) % 4
                s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=uid, indice_elegido=elegido, es_correcta=bool(acierta),
                                    fecha=ahora - timedelta(days=dias, hours=3) + timedelta(minutes=2)))
            for dias in perfil["dias"] + perfil.get("dias_previos", []):  # tiempo de uso: 3 sesiones de ~20 minutos al día
                for sesion in range(3):
                    base = ahora - timedelta(days=dias, hours=2 + sesion * 3)
                    for minuto in range(0, 20, 2):
                        s.add(Actividad(usuario_id=uid, fecha=base - timedelta(minutes=minuto)))
            if perfil["mensajes"]:
                chat = Conversacion(alumno_id=uid, tema_id=temas[BANCO[3][0]], titulo="Dudas de unidades", tipo="chat",
                                    fecha=ahora - timedelta(days=2))
                s.add(chat)
                s.flush()
                for k in range(perfil["mensajes"]):
                    s.add(Mensaje(conversacion_id=chat.id, rol="user", contenido="¿Cómo convierto pulgadas a milímetros?",
                                  fecha=ahora - timedelta(days=1 + k % 5)))
                    s.add(Mensaje(conversacion_id=chat.id, rol="assistant", contenido="Multiplica por 25.4: 1 in = 25.4 mm.",
                                  fecha=ahora - timedelta(days=1 + k % 5)))
        # dos alumnos preguntaron lo que el material no cubre: aparece «Falta material»
        for clave in ("luis", "sofia"):
            s.add(PreguntaSinRespuesta(alumno_id=ids[clave], tema_id=temas["Tolerancia y dimensionamiento geométrico"],
                                       pregunta="¿Qué significa el símbolo de concentricidad en un plano?",
                                       fecha=ahora - timedelta(days=2)))
        clase_id, maestro_id = clase.id, ids["maestro"]
        tema_conv, tema_tol = temas["Conversión entre Sistemas de Unidades de Medida"], temas["Tolerancia y dimensionamiento geométrico"]

    r1 = tareas.crear(maestro_id, clase_id, tema_conv, "preguntas", 5, ahora + timedelta(days=3), "Repasen la tabla de conversiones.")
    r2 = tareas.crear(maestro_id, clase_id, tema_tol, "nivel", 2, ahora + timedelta(days=8))
    print("Tareas:", r1[1], "|", r2[1])
    print(f"\nDemostración lista. Contraseña de todas las cuentas: {PASSWORD_DEMO}")
    for _clave, (nombre, email, rol) in CUENTAS.items():
        print(f"  {rol:8} {email:26} {nombre}")
    print(f"Clase «{NOMBRE_CLASE}», código para unirse: {CODIGO_CLASE}")


if __name__ == "__main__":
    borrar() if "--borrar" in sys.argv else crear()
