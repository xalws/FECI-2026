import unittest

import helpers  # noqa: F401  (configura la base temporal)

from core import examen, niveles, quiz
from core.db import get_session
from models.schema import Quiz, RespuestaQuiz
from test_base_datos import BaseDatos


def tema(i, resp, nivel=None):
    # Un tema como lo devuelve niveles.avance_materia (resp = [(dificultad, acertó)]).
    return {"id": i, "nombre": f"T{i}", **niveles.calcular_estado(resp, [])}


def avance(*unidades):
    return {"unidades": [{"nombre": f"U{n}", "temas": ts} for n, ts in enumerate(unidades, 1)]}


class TestSiguienteRecomendado(unittest.TestCase):
    def test_orden_refuerzo_luego_en_curso_luego_nuevo(self):
        malo = tema(1, [(4, True), (4, True)] + [(4, False)] * 6)       # precisión baja -> refuerzo
        en_curso = tema(2, [(3, True), (3, True), (3, True)])          # 9 XP: Intermedio
        dominado = tema(3, [(4, True)] * 4)                            # 16 XP: Avanzado -> no se recomienda
        nuevo1, nuevo2 = tema(4, []), tema(5, [])
        r = niveles.siguiente_recomendado(avance([nuevo1, malo], [dominado, en_curso, nuevo2]), limite=3)
        self.assertEqual([x["tema_id"] for x in r], [1, 2, 4])
        self.assertIn("precisión es baja", r[0]["razon"])
        self.assertIn("Continúa", r[1]["razon"])
        self.assertIn("XP para el siguiente nivel", r[1]["razon"])
        self.assertIn("Empieza", r[2]["razon"])

    def test_solo_recomienda_temas_con_material(self):
        t1, t2 = tema(1, []), tema(2, [])
        r = niveles.siguiente_recomendado(avance([t1, t2]), con_material={2})
        self.assertEqual([x["tema_id"] for x in r], [2])
        self.assertEqual(niveles.siguiente_recomendado(avance([t1, t2]), con_material=set()), [])

    def test_con_todo_dominado_no_hay_sugerencias(self):
        self.assertEqual(niveles.siguiente_recomendado(avance([tema(1, [(4, True)] * 4)])), [])

    def test_respeta_el_limite(self):
        self.assertEqual(len(niveles.siguiente_recomendado(avance([tema(i, []) for i in range(10)]), limite=2)), 2)


class TestRepasoDeErrores(BaseDatos):
    def _responder(self, pregunta, acierta):
        with get_session() as s:
            q = Quiz(conversacion_id=1, tema_id=self.tema_id, pregunta=pregunta, opciones=["a", "b", "c", "d"],
                     indice_correcto=0, explicacion="porque sí", dificultad=None)
            s.add(q)
            s.flush()
            qid = q.id
        quiz.evaluar(qid, self.alumno_id, 0 if acierta else 1)
        return qid

    def test_solo_cuenta_lo_que_sigue_mal(self):
        mal = self._responder("falla y sigue mal", False)
        corregida = self._responder("falla y luego acierta", False)
        quiz.evaluar(corregida, self.alumno_id, 0)  # la vuelve a contestar bien
        self._responder("siempre bien", True)
        pend = quiz.preguntas_pendientes(self.alumno_id, self.tema_id)
        self.assertIn(mal, [p["id"] for p in pend])
        self.assertNotIn(corregida, [p["id"] for p in pend])
        self.assertNotIn("siempre bien", [p["pregunta"] for p in pend])
        self.assertEqual(pend[0]["explicacion"], "porque sí")

    def test_los_fallos_mas_recientes_van_primero_y_hay_limite(self):
        ids = [self._responder(f"fallo {i}", False) for i in range(4)]
        pend = quiz.preguntas_pendientes(self.alumno_id, self.tema_id, limite=2)
        self.assertEqual([p["id"] for p in pend], [ids[3], ids[2]])

    def test_otro_alumno_o_tema_no_se_mezclan(self):
        self._responder("mío", False)
        self.assertEqual(quiz.preguntas_pendientes(self.alumno_id + 999, self.tema_id), [])
        self.assertEqual(quiz.preguntas_pendientes(self.alumno_id, self.tema_id + 999), [])


class TestRepasoEnElExamen(unittest.TestCase):
    PREGUNTAS = [{"id": 1, "pregunta": "p1", "opciones": list("abcd"), "indice_correcto": 0, "explicacion": "e",
                  "dificultad": None},
                 {"id": 2, "pregunta": "p2", "opciones": list("abcd"), "indice_correcto": 1, "explicacion": "e",
                  "dificultad": 3}]

    def test_el_repaso_usa_las_preguntas_dadas_y_no_genera_nuevas(self):
        ex = examen.nuevo_repaso(self.PREGUNTAS, "normal")
        self.assertEqual((ex["tipo"], ex["total"], len(ex["cola"])), ("repaso", 2, 2))
        examen.registrar_resultado(ex, True)
        examen.registrar_resultado(ex, False)
        self.assertTrue(examen.terminado(ex))

    def test_resumen_del_repaso(self):
        ex = examen.nuevo_repaso(self.PREGUNTAS, "normal")
        examen.registrar_resultado(ex, True)
        examen.registrar_resultado(ex, False)
        texto = examen.resumen_repaso(ex)
        self.assertIn("corregiste 1 de 2", texto)
        self.assertIn("sigue pendiente", texto)

    def test_el_resumen_normal_tolera_preguntas_sin_dificultad(self):
        ex = examen.nuevo_repaso(self.PREGUNTAS, "normal")
        ex["resultados"] = [{"numero": 1, "dificultad": None, "acerto": True}]
        self.assertIn("1/1", examen.resumen_texto(ex))


if __name__ == "__main__":
    unittest.main()
