import unittest

import helpers  # noqa: F401  (configura la base temporal)

from core import examen


def con(aciertos: int, total: int) -> dict:
    ex = examen.nuevo_examen(total, "normal")
    for i in range(total):
        examen.registrar_resultado(ex, i < aciertos)
    return ex


class TestRecomendacion(unittest.TestCase):
    def test_segun_el_puntaje(self):
        self.assertIn("Dominas este tema", examen.recomendacion(con(5, 5)))
        self.assertIn("Dominas este tema", examen.recomendacion(con(4, 5)))       # 80 %
        self.assertIn("Vas bien", examen.recomendacion(con(3, 5)))
        self.assertIn("repasar el tema antes de otro examen", examen.recomendacion(con(1, 5)))

    def test_menciona_las_falladas_y_donde_estan(self):
        self.assertNotIn("Repasar errores", examen.recomendacion(con(5, 5)))
        self.assertIn("La que fallaste está en «Repasar errores»", examen.recomendacion(con(4, 5)))
        self.assertIn("Las 3 que fallaste están", examen.recomendacion(con(2, 5)))

    def test_sin_resultados_no_dice_nada(self):
        self.assertEqual(examen.recomendacion(examen.nuevo_examen(5, "normal")), "")


if __name__ == "__main__":
    unittest.main()
