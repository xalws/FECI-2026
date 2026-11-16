import unittest

import helpers  # noqa: F401  (configura la base temporal)

from core import examen, niveles, reticula
from core.db import get_session
from models.schema import IntentoEjercicio, Quiz, RespuestaQuiz
from test_base_datos import BaseDatos
from test_reticula_examen import RETICULA


class TestCalculoDeNiveles(unittest.TestCase):
    def test_xp_por_respuesta_depende_de_la_dificultad(self):
        self.assertEqual([niveles.xp_respuesta(d, True) for d in (1, 2, 3, 4)], [1, 2, 3, 4])
        self.assertEqual(niveles.xp_respuesta(4, False), 0)
        self.assertEqual(niveles.xp_respuesta(None, True), niveles.DIFICULTAD_SIN_DATO)

    def test_xp_de_ejercicios(self):
        self.assertEqual([niveles.xp_ejercicio(p) for p in (0, 2, 3, 6, 9, 10)], [0, 0, 1, 2, 3, 3])

    def test_umbrales_de_nivel(self):
        self.assertEqual([niveles.nivel_por_xp(x) for x in (0, 1, 5, 6, 13, 14, 23, 24, 99)],
                         [0, 1, 1, 2, 2, 3, 3, 4, 4])

    def test_estado_sin_actividad(self):
        e = niveles.calcular_estado([], [])
        self.assertEqual((e["nivel"], e["nombre_nivel"], e["porcentaje"], e["siguiente_xp"]), (0, "Sin empezar", 0, 1))

    def test_estado_con_aciertos_y_ejercicios(self):
        # 3 aciertos a dificultad 4 (12 XP) + 1 a dificultad 2 (2 XP) = 14 -> Avanzado; el ejercicio 9/10 suma 3
        e = niveles.calcular_estado([(4, True)] * 3 + [(2, True)], [9])
        self.assertEqual((e["xp"], e["nivel"], e["nombre_nivel"]), (17, 3, "Avanzado"))
        self.assertEqual(e["siguiente_xp"], 24)

    def test_nivel_maximo_no_tiene_siguiente(self):
        self.assertIsNone(niveles.calcular_estado([(4, True)] * 6, [])["siguiente_xp"])

    def test_poca_precision_limita_el_nivel(self):
        respuestas = [(4, True)] * 2 + [(4, False)] * 6  # 25% de aciertos
        e = niveles.calcular_estado(respuestas, [])
        self.assertTrue(e["limitado"])
        self.assertEqual((e["xp"], e["xp_efectivo"], e["nivel"]), (8, 5, 1))

    def test_la_precision_no_limita_con_pocos_intentos(self):
        e = niveles.calcular_estado([(4, True), (4, True), (4, False)], [])
        self.assertFalse(e["limitado"])
        self.assertEqual(e["nivel"], 2)

    def test_texto_de_progreso_del_examen(self):
        despues = niveles.calcular_estado([(3, True)] * 2, [])
        texto = examen.progreso_texto(0, 0, despues)
        self.assertIn("+6", texto)
        self.assertIn("Intermedio", texto)
        self.assertIn("Subiste de nivel", texto)
        self.assertNotIn("Subiste", examen.progreso_texto(2, 6, despues))


class TestAvanceDeMateria(BaseDatos):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        r = reticula.crear_desde_reticula(RETICULA, f"U niveles {cls.__name__}", "Carrera", "Cuatrimestre 1")
        cls.materia_id = r["materia_id"]
        cls.temas = reticula.temas_de_materia(cls.materia_id)  # Leyes básicas, Circuitos resistivos, Mallas y nodos

    def _responder(self, tema_id, dificultad, correcta):
        with get_session() as s:
            q = Quiz(conversacion_id=1, tema_id=tema_id, pregunta="p", opciones=["a", "b", "c", "d"],
                     indice_correcto=0, explicacion="", dificultad=dificultad)
            s.add(q)
            s.flush()
            s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=self.alumno_id, indice_elegido=0, es_correcta=correcta))

    def test_avance_por_unidad_en_el_orden_de_la_reticula(self):
        a = self.temas[0]["id"]
        for dif in (4, 4, 4, 2):
            self._responder(a, dif, True)
        with get_session() as s:
            s.add(IntentoEjercicio(alumno_id=self.alumno_id, tema_id=a, enunciado="e", respuesta="r", puntaje=9))
        av = niveles.avance_materia(self.alumno_id, self.materia_id)
        self.assertEqual([u["nombre"] for u in av["unidades"]], ["Principios y leyes", "Análisis en CD"])
        u1, u2 = av["unidades"]
        self.assertEqual([t["nombre"] for t in u1["temas"]], ["Leyes básicas", "Circuitos resistivos"])
        leyes, resistivos = u1["temas"]
        self.assertEqual((leyes["xp"], leyes["nivel"], leyes["nombre_nivel"]), (17, 3, "Avanzado"))
        self.assertEqual(resistivos["nivel"], 0)
        self.assertEqual(u1["nivel"], 1)                      # promedio de 3 y 0 = 1,5 -> 1
        self.assertEqual(u1["porcentaje"], round((round(17 / 24 * 100) + 0) / 2))
        self.assertEqual((u2["nivel"], u2["porcentaje"]), (0, 0))  # unidad sin empezar
        self.assertEqual(av["xp"], 17)
        self.assertEqual(av["materia"], "Circuitos Eléctricos")

    def test_estado_de_un_tema(self):
        b = self.temas[1]["id"]
        self.assertEqual(niveles.estado_tema(self.alumno_id, b)["nivel"], 0)
        self._responder(b, 3, True)
        self.assertEqual(niveles.estado_tema(self.alumno_id, b)["xp"], 3)

    def test_materias_disponibles_y_con_actividad(self):
        self.assertIn(self.materia_id, niveles.materias_disponibles())
        self.assertTrue(niveles.materias_disponibles()[self.materia_id].startswith("Circuitos Eléctricos"))
        self._responder(self.temas[2]["id"], 2, False)
        self.assertIn(self.materia_id, niveles.materias_con_actividad(self.alumno_id))

    def test_tabla_para_el_maestro(self):
        self._responder(self.temas[0]["id"], 4, True)
        df = niveles.tabla_avance(self.materia_id, {self.alumno_id: "Alumno"})
        self.assertEqual(list(df["alumno"]), ["Alumno"])
        self.assertIn("% Principios y leyes", df.columns)
        self.assertIn("% Análisis en CD", df.columns)


if __name__ == "__main__":
    unittest.main()
