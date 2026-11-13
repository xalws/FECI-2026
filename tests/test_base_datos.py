import unittest
from unittest import mock

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import chat, progreso, quiz, stats
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import (Carrera, Cuatrimestre, Materia, Quiz, RespuestaQuiz, Tema, Unidad,
                           Universidad, Usuario)


class BaseDatos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            uni = Universidad(nombre=f"U de prueba {cls.__name__}")  # nombre único por clase
            s.add(uni)
            s.flush()
            car = Carrera(nombre="C", universidad_id=uni.id)
            s.add(car)
            s.flush()
            cua = Cuatrimestre(nombre="Q1", carrera_id=car.id)
            s.add(cua)
            s.flush()
            mat = Materia(nombre="M", cuatrimestre_id=cua.id)
            s.add(mat)
            s.flush()
            uni_t = Unidad(nombre="U1", materia_id=mat.id)
            s.add(uni_t)
            s.flush()
            tema = Tema(nombre="T1", unidad_id=uni_t.id)
            s.add(tema)
            alumno = Usuario(nombre="Alumno", email=f"{cls.__name__}@test.local", password_hash=hash_password("x"), rol="alumno")
            s.add(alumno)
            s.flush()
            cls.tema_id, cls.alumno_id = tema.id, alumno.id

    def _quiz(self, pregunta, correcta_idx=0):
        with get_session() as s:
            q = Quiz(conversacion_id=1, tema_id=self.tema_id, pregunta=pregunta, opciones=["a", "b", "c", "d"],
                     indice_correcto=correcta_idx, explicacion="e")
            s.add(q)
            s.flush()
            return q.id


class TestQuizYProgreso(BaseDatos):
    def test_evaluar_y_nivel(self):
        for i in range(4):  # 4 respuestas, todas incorrectas
            qid = self._quiz(f"nivel-{i}")
            r = quiz.evaluar(qid, self.alumno_id, 1)
            self.assertFalse(r["es_correcta"])
            self.assertEqual(r["indice_correcto"], 0)
        p = progreso.progreso_tema(self.alumno_id, self.tema_id)
        self.assertEqual(p["nivel"], "apoyo")
        resumen = progreso.resumen_alumno(self.alumno_id)
        self.assertEqual(resumen[0]["tema"], "T1")

    def test_ejercicios_calificados(self):
        self.assertEqual(progreso.resumen_ejercicios(self.alumno_id)["intentos"], 0)
        progreso.guardar_intento(self.alumno_id, self.tema_id, "enunciado", "respuesta", 8, "bien")
        progreso.guardar_intento(self.alumno_id, self.tema_id, "enunciado 2", "respuesta 2", 6, "regular")
        r = progreso.resumen_ejercicios(self.alumno_id)
        self.assertEqual((r["intentos"], r["promedio"]), (2, 7.0))


class TestQuizEnfocado(BaseDatos):
    def test_prioriza_lo_fallado_y_evita_repetir(self):
        fallada = self._quiz("¿Pregunta fallada enfocada?")
        quiz.evaluar(fallada, self.alumno_id, 1)  # incorrecta
        acertada = self._quiz("¿Pregunta acertada enfocada?")
        quiz.evaluar(acertada, self.alumno_id, 0)  # correcta

        frag_fallo = {"texto": "material de lo fallado", "score": 0.9, "archivo": "a.pdf", "pagina": 2}
        azar = [{"texto": "material de lo fallado", "score": 1.0, "archivo": "", "pagina": ""},
                {"texto": "otro material", "score": 1.0, "archivo": "", "pagina": ""}]
        with mock.patch.object(quiz.rag, "buscar", return_value=[frag_fallo]) as buscar, \
                mock.patch.object(quiz.rag, "chunks_aleatorios", return_value=azar):
            fragmentos = quiz._fragmentos_para_quiz(self.tema_id, self.alumno_id)
        self.assertIn("¿Pregunta fallada enfocada?", [c.args[1] for c in buscar.call_args_list])
        textos = [f["texto"] for f in fragmentos]
        self.assertEqual(textos[0], "material de lo fallado")   # primero, el de lo fallado
        self.assertEqual(len(textos), len(set(textos)))         # sin duplicados

    def test_crear_quiz_pasa_las_preguntas_a_evitar(self):
        quiz.evaluar(self._quiz("¿Ya contestada para evitar?"), self.alumno_id, 0)
        generado = {"pregunta": "nueva", "opciones": ["1", "2", "3", "4"], "indice_correcto": 2,
                    "explicacion": "porque"}
        with mock.patch.object(quiz.rag, "buscar", return_value=[]), \
                mock.patch.object(quiz.rag, "chunks_aleatorios",
                                  return_value=[{"texto": "x", "score": 1.0, "archivo": "", "pagina": ""}]), \
                mock.patch.object(quiz.llm, "generar_quiz", return_value=generado) as gen:
            q = quiz.crear_quiz(self.tema_id, 1, 3, self.alumno_id)
        self.assertEqual(q["pregunta"], "nueva")
        self.assertEqual(q["dificultad"], 3)
        self.assertEqual(gen.call_args.args[1], 3)  # la dificultad llega a la IA
        self.assertIn("¿Ya contestada para evitar?", gen.call_args.args[2])
        with get_session() as s:
            self.assertEqual(s.get(Quiz, q["id"]).dificultad, 3)

    def test_sin_material_no_hay_quiz(self):
        with mock.patch.object(quiz.rag, "chunks_aleatorios", return_value=[]), \
                mock.patch.object(quiz.rag, "buscar", return_value=[]):
            self.assertIsNone(quiz.crear_quiz(self.tema_id, 1, 2, self.alumno_id))


class TestSinRespuesta(BaseDatos):
    def test_se_guarda_y_aparece_para_el_maestro(self):
        chat.registrar_sin_respuesta(self.alumno_id, self.tema_id, "¿Pregunta fuera del material?")
        df = stats.preguntas_sin_respuesta()
        self.assertIn("¿Pregunta fuera del material?", list(df["pregunta"]))
        self.assertEqual(stats.preguntas_sin_respuesta([-1]).shape[0], 0)  # filtra por materia


if __name__ == "__main__":
    unittest.main()
