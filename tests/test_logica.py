import unittest
from datetime import datetime, timedelta, timezone

import helpers  # noqa: F401  (configura la base temporal)
import pandas as pd

from core import actividad, llm, progreso, sospechas, stats

T0 = datetime(2026, 11, 1, tzinfo=timezone.utc)


class TestLlm(unittest.TestCase):
    def test_latex_se_convierte_a_formato_de_streamlit(self):
        texto = r"Fórmula \[ V = I R \] y en línea \( P = V I \)."
        self.assertEqual(llm._formato_latex(texto), "Fórmula $$V = I R$$ y en línea $P = V I$.")

    def test_sin_fragmentos_no_llama_a_la_ia(self):
        self.assertEqual(llm.responder("Tema", "¿algo?", [], []), llm.SIN_INFO)

    def test_sin_api_key_el_error_es_claro(self):
        with self.assertRaises(RuntimeError) as e:
            llm.responder("Tema", "pregunta", [{"texto": "x"}], [])
        self.assertIn("GROQ_API_KEY", str(e.exception))


class TestProgreso(unittest.TestCase):
    def test_niveles(self):
        self.assertEqual(progreso._nivel(2, 0), "normal")      # pocos intentos: no opina
        self.assertEqual(progreso._nivel(10, 30), "apoyo")
        self.assertEqual(progreso._nivel(10, 50), "normal")
        self.assertEqual(progreso._nivel(10, 80), "avanzado")


class TestActividad(unittest.TestCase):
    def test_las_pausas_largas_no_cuentan(self):
        marcas = [T0, T0 + timedelta(minutes=2), T0 + timedelta(minutes=3),
                  T0 + timedelta(minutes=30), T0 + timedelta(minutes=31)]
        self.assertEqual(actividad.segundos_de_uso(marcas), 240)

    def test_sin_marcas(self):
        self.assertEqual(actividad.segundos_de_uso([]), 0)


def _respuestas(alumno_id, nombre, n, tarda, entre, correctas):
    filas = []
    for i in range(n):
        q = T0 + timedelta(seconds=i * entre)
        filas.append(dict(alumno_id=alumno_id, alumno=nombre, es_correcta=correctas(i),
                          fecha_resp=q + timedelta(seconds=tarda), fecha_quiz=q,
                          pregunta="¿Qué es x?", opciones="[a, b, c, d]", materia_id=1))
    return filas


class TestSospechas(unittest.TestCase):
    def test_respuestas_rapidas_y_rafaga(self):
        df = pd.DataFrame(_respuestas(1, "Ana", 6, tarda=2, entre=10, correctas=lambda i: True))
        r = sospechas.evaluar(df)
        self.assertEqual(list(r["alumno"]), ["Ana"])
        self.assertIn("más rápidas", r.iloc[0]["motivos"])
        self.assertIn("en menos de", r.iloc[0]["motivos"])

    def test_alumno_normal_no_se_marca(self):
        df = pd.DataFrame(_respuestas(2, "Beto", 6, tarda=40, entre=300, correctas=lambda i: i % 2 == 0))
        self.assertTrue(sospechas.evaluar(df).empty)

    def test_mejora_brusca(self):
        df = pd.DataFrame(_respuestas(3, "Carla", 10, tarda=40, entre=300, correctas=lambda i: i >= 5))
        r = sospechas.evaluar(df)
        self.assertIn("mejora brusca", r.iloc[0]["motivos"])

    def test_sin_datos(self):
        self.assertTrue(sospechas.evaluar(pd.DataFrame()).empty)


class TestResumenCsv(unittest.TestCase):
    def test_resumen_por_alumno(self):
        msgs = pd.DataFrame({"alumno": ["Ana", "Ana", "Beto"], "rol": ["user", "assistant", "user"]})
        resp = pd.DataFrame({"alumno": ["Ana", "Ana"], "es_correcta": [True, False]})
        r = stats.resumen_por_alumno(msgs, resp, {"Ana": 12.5})
        ana = r[r["alumno"] == "Ana"].iloc[0]
        self.assertEqual((ana["preguntas"], ana["quizzes"], ana["% aciertos"], ana["minutos en la app"]),
                         (1, 2, 50.0, 12.5))
        self.assertTrue(pd.isna(r[r["alumno"] == "Beto"].iloc[0]["% aciertos"]))


if __name__ == "__main__":
    unittest.main()
