import re
import unittest

import helpers  # noqa: F401  (configura la base temporal)
from core import estudiante


class TestAnimacionesDeCarga(unittest.TestCase):
    def test_hay_once_animaciones(self):
        self.assertEqual(len(estudiante.VARIANTES), 11)
        self.assertIn("libro", estudiante.VARIANTES)

    def test_cada_html_es_una_sola_linea_y_segura(self):
        for nombre in estudiante.VARIANTES:
            h = estudiante.estudiante_html(nombre)
            self.assertNotIn("\n", h, nombre)
            self.assertNotIn("<script", h, nombre)
            self.assertTrue(h.startswith('<div class="tu-est"'), nombre)
            self.assertIn("viewBox", h, nombre)

    def test_las_animaciones_usadas_en_el_html_existen_en_el_css(self):
        css = estudiante.CSS_ESTUDIANTE
        for nombre in estudiante.VARIANTES:
            for clase in set(re.findall(r'class="((?:c|est)-[a-z0-9-]+)', estudiante.estudiante_html(nombre))):
                self.assertIn(f".{clase}", css, f"{nombre}: {clase}")
        for usada in set(re.findall(r"animation:([a-z0-9-]+)", css)) | set(re.findall(r"animation-name:([a-z0-9-]+)", css)):
            self.assertIn(f"@keyframes {usada}{{", css, usada)

    def test_ciclos_calculados_empalman(self):
        for nombre in ("est-bob", "est-torso", "est-pila", "c-vuelo", "c-orbita", "c-escribe"):
            if f"@keyframes {nombre}{{" not in estudiante.CSS_ESTUDIANTE:
                continue
            cuerpo = estudiante.CSS_ESTUDIANTE.split(f"@keyframes {nombre}{{")[1].split("}}")[0]
            cuadros = [c.split("{", 1)[1] if "{" in c else c for c in cuerpo.split("}")]
            if nombre != "c-escribe":  # el lápiz arranca invisible y termina invisible: otra comprobación
                self.assertEqual(cuadros[0].replace("-0.00", "0.00"), cuadros[-1].replace("-0.00", "0.00"), nombre)

    def test_elegir_no_repite_la_anterior(self):
        for ultima in estudiante.VARIANTES:
            for _ in range(30):
                self.assertNotEqual(estudiante.elegir(ultima), ultima)

    def test_css_sin_menor_que_seguido_de_letra(self):
        self.assertIsNone(re.search(r"<[a-zA-Z]", estudiante.CSS_ESTUDIANTE))


if __name__ == "__main__":
    unittest.main()
