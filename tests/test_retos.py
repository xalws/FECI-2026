import unittest
from datetime import date, timedelta

import helpers  # noqa: F401  (configura la base temporal)
from core import hoy, retos

LUNES = date(2026, 11, 16)  # lunes


class TestRetos(unittest.TestCase):
    def test_el_reto_es_el_mismo_toda_la_semana_y_cambia_el_lunes(self):
        r = [retos.reto_de_semana(LUNES + timedelta(days=d)) for d in range(7)]
        self.assertEqual(len({x["id"] for x in r}), 1)
        self.assertEqual(r[0]["lunes"], LUNES)
        self.assertEqual(r[0]["termina"], LUNES + timedelta(days=6))
        siguiente = retos.reto_de_semana(LUNES + timedelta(days=7))
        self.assertNotEqual(siguiente["id"], r[0]["id"])

    def test_todos_los_retos_salen_con_el_tiempo(self):
        vistos = {retos.reto_de_semana(LUNES + timedelta(weeks=w))["id"] for w in range(len(retos.RETOS) * 2)}
        self.assertEqual(vistos, {r[0] for r in retos.RETOS})

    def test_dias_para_reiniciar(self):
        self.assertEqual(retos.dias_para_reiniciar(LUNES), 7)
        self.assertEqual(retos.dias_para_reiniciar(LUNES + timedelta(days=6)), 1)

    def test_valores_de_la_semana(self):
        d = lambda n: LUNES + timedelta(days=n)  # noqa: E731
        v = retos.valores_de_semana(LUNES, [d(0), d(1), d(1), d(8)], [d(2)], {d(0): 30.0, d(2): 15.0, d(9): 50.0, d(3): 0.0},
                                    [(d(0), 3), (d(1), 2), (d(8), 9)])
        self.assertEqual(v, {"preguntas_semana": 3, "ejercicios_semana": 1, "dias_semana": 2, "minutos_semana": 45,
                             "xp_semana_actual": 5})

    def test_retos_cumplidos_en_semanas_pasadas(self):
        # Una semana que cumple justo el reto que le tocaba y otra que no
        buena = LUNES
        reto = retos.reto_de_semana(buena)
        resp = [buena] * reto["meta"] if reto["clave"] == "preguntas_semana" else []
        ejer = [buena] * reto["meta"] if reto["clave"] == "ejercicios_semana" else []
        minutos = {buena + timedelta(days=i): float(max(1, reto["meta"] // 4 + 1)) for i in range(7)} \
            if reto["clave"] in ("dias_semana", "minutos_semana") else {}
        xp = [(buena, reto["meta"])] if reto["clave"] == "xp_semana_actual" else []
        self.assertGreaterEqual(retos.retos_cumplidos(resp, ejer, minutos, xp), 1)
        self.assertEqual(retos.retos_cumplidos([LUNES], [], {}, []), 0)  # una pregunta no cumple ningún reto
        self.assertEqual(retos.retos_cumplidos([], [], {}, []), 0)

    def test_avance_semana(self):
        r = retos.reto_de_semana(LUNES)
        self.assertEqual(retos.avance_semana({r["clave"]: 7}, LUNES), 7)
        self.assertEqual(retos.avance_semana({}, LUNES), 0)


class TestRecordatorios(unittest.TestCase):
    def test_racha_en_riesgo(self):
        self.assertTrue(hoy.racha_en_riesgo(5, 0))
        self.assertFalse(hoy.racha_en_riesgo(5, 12.0))  # ya estudió hoy
        self.assertFalse(hoy.racha_en_riesgo(1, 0))  # una racha de un día no se «pierde»
        self.assertFalse(hoy.racha_en_riesgo(0, 0))


if __name__ == "__main__":
    unittest.main()
