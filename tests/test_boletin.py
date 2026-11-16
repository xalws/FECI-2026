import unittest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from zoneinfo import ZoneInfo

import helpers  # noqa: F401  (configura la base temporal)
from openpyxl import load_workbook
from sqlalchemy import select

from core import boletin
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import (Actividad, Asignacion, Carrera, Clase, Conversacion, Cuatrimestre, Inscripcion, Materia, Mensaje,
                           PreguntaSinRespuesta, Quiz, RespuestaQuiz, Tema, Unidad, Universidad, Usuario)

AHORA = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
ZONA = ZoneInfo("America/Ciudad_Juarez")


def hace(dias, horas=0):
    return AHORA - timedelta(days=dias, hours=horas)


def datos(**cambios):
    """Una clase de 6 alumnos con una semana conocida."""
    raw = {
        "clase": {"id": 1, "nombre": "Grupo A", "materia": "Circuitos"},
        "alumnos": {1: "Ana", 2: "Beto", 3: "Carla", 4: "Dani", 5: "Eli", 6: "Fer"},
        "temas": {10: "Ley de Ohm", 11: "Leyes de Kirchhoff"},
        "mensajes": [(1, hace(1)), (1, hace(2)), (2, hace(3)), (2, hace(10))],
        # Ana 6/6 (destacada), Beto 1/4 (necesita apoyo), Carla 2/2 (pocas respuestas: no se juzga)
        "quizzes": [(1, 10, True, hace(1, i)) for i in range(6)]
                   + [(2, 11, False, hace(2, i)) for i in range(3)] + [(2, 11, True, hace(2, 5))]
                   + [(3, 10, True, hace(1)), (3, 10, True, hace(1, 2))]
                   + [(4, 10, True, hace(9))],               # Dani: solo la semana anterior
        "ejercicios": [],
        "marcas": [(1, hace(1)), (1, hace(1) + timedelta(minutes=2)), (1, hace(2)), (2, hace(3)), (5, hace(30))],
        "ultima": {4: hace(9), 5: hace(30)},
        "sin_respuesta": [(11, 2, hace(2)), (11, 3, hace(3)), (10, 1, hace(4)), (10, 1, hace(20))],
        "tareas": [{"tema": "Ley de Ohm", "descripcion": "Responder 5 preguntas de examen", "fecha_limite": hace(2),
                    "hechas": 2, "alumnos": 6},
                   {"tema": "Leyes de Kirchhoff", "descripcion": "Resolver 2 ejercicios", "fecha_limite": AHORA + timedelta(days=3),
                    "hechas": 1, "alumnos": 6},
                   {"tema": "Ley de Ohm", "descripcion": "Muy lejana", "fecha_limite": AHORA + timedelta(days=30),
                    "hechas": 0, "alumnos": 6},
                   {"tema": "Ley de Ohm", "descripcion": "Antigua", "fecha_limite": hace(40), "hechas": 6, "alumnos": 6}],
    }
    raw.update(cambios)
    return raw


class TestResumen(unittest.TestCase):
    def setUp(self):
        self.b = boletin.resumir(datos(), AHORA, ZONA)
        self.por = {f["alumno"]: f for f in self.b["alumnos"]}

    def test_estado_de_cada_alumno(self):
        self.assertEqual(self.por["Ana"]["estado"], "Destacado")
        self.assertEqual(self.por["Beto"]["estado"], "Necesita apoyo")
        self.assertIn("25%", self.por["Beto"]["motivo"])
        self.assertEqual(self.por["Carla"]["estado"], "Al día")           # 2 respuestas: pocas para juzgar
        self.assertEqual(self.por["Dani"]["estado"], "Sin actividad")     # solo estuvo la semana anterior
        self.assertIn("07/11", self.por["Dani"]["motivo"])                # cuándo fue la última vez
        self.assertEqual(self.por["Eli"]["estado"], "Sin actividad")
        self.assertEqual(self.por["Fer"]["estado"], "Aún no entra")

    def test_cifras_de_un_alumno(self):
        ana = self.por["Ana"]
        self.assertEqual((ana["preguntas"], ana["quizzes"], ana["aciertos"]), (2, 6, 100))
        self.assertEqual(ana["días activos"], 2)
        self.assertEqual(ana["minutos"], 2.0)                             # solo cuenta el rato entre dos marcas seguidas
        self.assertIsNone(self.por["Fer"]["aciertos"])

    def test_orden_primero_a_quien_hay_que_buscar(self):
        estados = [f["estado"] for f in self.b["alumnos"]]
        self.assertEqual(estados, sorted(estados, key=boletin.ESTADOS.index))
        self.assertEqual([f["alumno"] for f in self.b["necesitan_apoyo"]], ["Beto", "Dani", "Eli", "Fer"])
        self.assertEqual([f["alumno"] for f in self.b["destacados"]], ["Ana"])

    def test_totales_y_comparacion_con_la_semana_anterior(self):
        s, p = self.b["semana"], self.b["anterior"]
        self.assertEqual((s["activos"], s["preguntas"], s["quizzes"]), (3, 3, 12))
        self.assertEqual(s["aciertos"], 75)                               # 9 de 12
        self.assertEqual((p["activos"], p["preguntas"], p["quizzes"], p["aciertos"]), (2, 1, 1, 100))

    def test_temas_flojos_piden_un_minimo_de_intentos(self):
        self.assertEqual(self.b["temas_flojos"], [{"tema": "Leyes de Kirchhoff", "intentos": 4, "% aciertos": 25}])

    def test_tareas_solo_las_de_la_semana_y_las_proximas(self):
        self.assertEqual([t["tarea"] for t in self.b["tareas"]], ["Responder 5 preguntas de examen", "Resolver 2 ejercicios"])
        self.assertEqual([t["vencida"] for t in self.b["tareas"]], [True, False])

    def test_material_faltante_del_ultimo_mes_no_cuenta(self):
        self.assertEqual(self.b["sin_respuesta"], [{"tema": "Leyes de Kirchhoff", "preguntas": 2},
                                                   {"tema": "Ley de Ohm", "preguntas": 1}])

    def test_fechas_del_periodo_en_hora_local(self):
        self.assertEqual((self.b["desde"].isoformat(), self.b["hasta"].isoformat()), ("2026-11-09", "2026-11-16"))

    def test_frases(self):
        texto = " ".join(self.b["frases"])
        self.assertIn("3 de 6 alumnos estuvieron activos (+1 contra la semana anterior)", texto)
        self.assertIn("Leyes de Kirchhoff", texto)
        self.assertIn("Beto, Dani, Eli, Fer", texto)
        self.assertIn("la cumplieron 2 de 6", texto)
        self.assertIn("Destacaron: Ana", texto)

    def test_clase_sin_alumnos_o_sin_actividad(self):
        vacio = boletin.resumir(datos(alumnos={}, mensajes=[], quizzes=[], marcas=[], ultima={}, sin_respuesta=[], tareas=[]),
                                AHORA, ZONA)
        self.assertEqual(vacio["frases"], ["La clase todavía no tiene alumnos."])
        quieta = boletin.resumir(datos(mensajes=[], quizzes=[], marcas=[], ultima={}, sin_respuesta=[], tareas=[]), AHORA, ZONA)
        self.assertIn("Nadie hizo preguntas ni quizzes en la semana.", quieta["frases"])
        self.assertIsNone(quieta["semana"]["aciertos"])
        self.assertEqual(quieta["semana"]["activos"], 0)

    def test_acepta_fechas_sin_zona(self):  # SQLite las devuelve así
        raw = datos(mensajes=[(1, hace(1).replace(tzinfo=None))], quizzes=[], marcas=[])
        b = boletin.resumir(raw, AHORA, ZONA)
        self.assertEqual({f["alumno"]: f["preguntas"] for f in b["alumnos"]}["Ana"], 1)

    def test_texto_y_excel(self):
        texto = boletin.como_texto(self.b)
        self.assertIn("Boletín semanal · Grupo A (Circuitos)", texto)
        self.assertIn("A quién buscar:", texto)
        self.assertIn("- Beto: Acertó 25%", texto)
        libro = load_workbook(BytesIO(boletin.como_excel(self.b)))
        self.assertEqual(libro.sheetnames, ["Resumen", "Alumnos", "Temas flojos", "Tareas", "Material faltante"])
        self.assertEqual(libro["Alumnos"].max_row, 7)  # encabezado + 6 alumnos


class TestConBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            uni = Universidad(nombre="U boletín")
            s.add(uni)
            s.flush()
            car = Carrera(nombre="C", universidad_id=uni.id)
            s.add(car)
            s.flush()
            cua = Cuatrimestre(nombre="Cuatrimestre 1", carrera_id=car.id)
            s.add(cua)
            s.flush()
            mat = Materia(nombre="Circuitos boletín", cuatrimestre_id=cua.id)
            s.add(mat)
            s.flush()
            uni_ = Unidad(nombre="U1", materia_id=mat.id)
            s.add(uni_)
            s.flush()
            tema = Tema(nombre="Ohm", unidad_id=uni_.id)
            s.add(tema)

            def usuario(nombre, email, rol):
                u = Usuario(nombre=nombre, email=email, rol=rol, password_hash=hash_password("clave123"))
                s.add(u)
                s.flush()
                return u.id
            cls.maestro = usuario("Prof Boletín", "prof@boletin.local", "maestro")
            cls.otro_maestro = usuario("Otro Prof", "otro@boletin.local", "maestro")
            cls.ana = usuario("Ana", "ana@boletin.local", "alumno")
            cls.beto = usuario("Beto", "beto@boletin.local", "alumno")
            cls.pendiente = usuario("Pendiente", "pend@boletin.local", "alumno")
            s.flush()
            s.add(Asignacion(maestro_id=cls.maestro, materia_id=mat.id))
            clase = Clase(nombre="Grupo boletín", materia_id=mat.id, maestro_id=cls.maestro, codigo="BOLET123")
            s.add(clase)
            s.flush()
            cls.clase_id, cls.tema_id = clase.id, tema.id
            s.add_all([Inscripcion(clase_id=clase.id, alumno_id=cls.ana, estado="activo"),
                       Inscripcion(clase_id=clase.id, alumno_id=cls.beto, estado="activo"),
                       Inscripcion(clase_id=clase.id, alumno_id=cls.pendiente, estado="pendiente")])
            ahora = datetime.now(timezone.utc)
            conv = Conversacion(alumno_id=cls.ana, tema_id=tema.id, titulo="x")
            s.add(conv)
            s.flush()
            s.add(Mensaje(conversacion_id=conv.id, rol="user", contenido="hola", fecha=ahora - timedelta(days=1)))
            s.add(Mensaje(conversacion_id=conv.id, rol="assistant", contenido="respuesta", fecha=ahora - timedelta(days=1)))
            quiz = Quiz(conversacion_id=conv.id, tema_id=tema.id, pregunta="¿?", opciones=["a", "b"], indice_correcto=0)
            s.add(quiz)
            s.flush()
            s.add(RespuestaQuiz(quiz_id=quiz.id, alumno_id=cls.ana, indice_elegido=0, es_correcta=True,
                                fecha=ahora - timedelta(days=2)))
            s.add(Actividad(usuario_id=cls.ana, fecha=ahora - timedelta(days=1)))
            s.add(PreguntaSinRespuesta(alumno_id=cls.ana, tema_id=tema.id, pregunta="¿algo?", fecha=ahora - timedelta(days=1)))

    def test_boletin_de_una_clase_real(self):
        b = boletin.generar(self.maestro, self.clase_id, ZONA)
        por = {f["alumno"]: f for f in b["alumnos"]}
        self.assertEqual(set(por), {"Ana", "Beto"})                       # la solicitud pendiente no cuenta
        self.assertEqual((por["Ana"]["preguntas"], por["Ana"]["quizzes"], por["Ana"]["aciertos"]), (1, 1, 100))
        self.assertEqual(por["Beto"]["estado"], "Aún no entra")
        self.assertEqual(b["semana"]["activos"], 1)
        self.assertEqual(b["sin_respuesta"], [{"tema": "Ohm", "preguntas": 1}])

    def test_solo_el_maestro_de_la_clase_o_un_admin(self):
        self.assertIsNone(boletin.generar(self.otro_maestro, self.clase_id, ZONA))
        self.assertIsNone(boletin.generar(self.maestro, 999999, ZONA))
        self.assertIsNone(boletin.generar(self.ana, self.clase_id, ZONA))  # un alumno no ve el boletín
        with get_session() as s:
            admin = s.scalar(select(Usuario.id).where(Usuario.rol == "admin"))
        self.assertIsNotNone(boletin.generar(admin, self.clase_id, ZONA))


if __name__ == "__main__":
    unittest.main()
