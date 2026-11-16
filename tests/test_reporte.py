"""Aviso de material faltante y reporte en Excel para el maestro."""
import unittest
from io import BytesIO

import helpers  # noqa: F401  (configura la base temporal)
import pandas as pd
from openpyxl import load_workbook

from core import stats


def sin_respuesta(filas):
    return pd.DataFrame(filas, columns=["pregunta", "fecha", "alumno", "tema", "materia"])


FECHA = pd.Timestamp("2026-11-15 19:37", tz="America/Ciudad_Juarez")


class TestMaterialFaltante(unittest.TestCase):
    def test_vacio(self):
        r = stats.material_faltante(sin_respuesta([]))
        self.assertTrue(r.empty)
        self.assertEqual(list(r.columns), ["materia", "tema", "alumnos", "preguntas", "ejemplo"])

    def test_un_solo_alumno_no_cuenta_aunque_pregunte_muchas_veces(self):
        r = stats.material_faltante(sin_respuesta([("p1", FECHA, "Ana", "Tema A", "Mat"),
                                                   ("p2", FECHA, "Ana", "Tema A", "Mat")]))
        self.assertTrue(r.empty)

    def test_varios_alumnos_en_el_mismo_tema_si_cuentan(self):
        r = stats.material_faltante(sin_respuesta([
            ("la más reciente", FECHA, "Ana", "Tema A", "Mat"), ("otra", FECHA, "Beto", "Tema A", "Mat"),
            ("repetida", FECHA, "Beto", "Tema A", "Mat"), ("suelta", FECHA, "Ana", "Tema B", "Mat")]))
        self.assertEqual(len(r), 1)
        fila = r.iloc[0]
        self.assertEqual((fila["tema"], fila["alumnos"], fila["preguntas"]), ("Tema A", 2, 3))
        self.assertEqual(fila["ejemplo"], "la más reciente")  # la consulta devuelve primero la más nueva

    def test_misma_materia_distinta_se_separa_y_se_ordena(self):
        filas = [("a", FECHA, "Ana", "T", "M1"), ("b", FECHA, "Beto", "T", "M1"),
                 ("c", FECHA, "Ana", "T", "M2"), ("d", FECHA, "Beto", "T", "M2"), ("e", FECHA, "Carla", "T", "M2")]
        r = stats.material_faltante(sin_respuesta(filas))
        self.assertEqual(list(r["materia"]), ["M2", "M1"])  # más alumnos primero
        self.assertEqual(list(r["alumnos"]), [3, 2])

    def test_el_minimo_se_puede_cambiar(self):
        filas = [("a", FECHA, "Ana", "T", "M")]
        self.assertEqual(len(stats.material_faltante(sin_respuesta(filas), minimo_alumnos=1)), 1)


class TestExcel(unittest.TestCase):
    def leer(self, hojas):
        return load_workbook(BytesIO(stats.exportar_excel(hojas)))

    def test_una_hoja_por_tabla_con_sus_datos(self):
        libro = self.leer({"Resumen": pd.DataFrame({"alumno": ["Ana", "Beto"], "minutos": [12.5, 3.0]}),
                           "Aciertos": pd.DataFrame({"tema": ["T"], "% aciertos": [80.0]})})
        self.assertEqual(libro.sheetnames, ["Resumen", "Aciertos"])
        hoja = libro["Resumen"]
        self.assertEqual([c.value for c in hoja[1]], ["alumno", "minutos"])
        self.assertEqual([c.value for c in hoja[2]], ["Ana", 12.5])
        self.assertEqual(hoja.max_row, 3)
        self.assertEqual(hoja.freeze_panes, "A2")
        self.assertTrue(hoja["A1"].font.bold)

    def test_fechas_con_zona_horaria_no_rompen_y_conservan_la_hora_local(self):
        libro = self.leer({"Sin respuesta": sin_respuesta([("¿algo?", FECHA, "Ana", "T", "M")])})
        celda = libro["Sin respuesta"]["B2"].value
        self.assertEqual((celda.year, celda.month, celda.day, celda.hour, celda.minute), (2026, 11, 15, 19, 37))

    def test_tabla_vacia_solo_lleva_encabezado(self):
        libro = self.leer({"Falta material": stats.material_faltante(sin_respuesta([]))})
        hoja = libro["Falta material"]
        self.assertEqual(hoja.max_row, 1)
        self.assertEqual(hoja["A1"].value, "materia")

    def test_nombres_de_hoja_invalidos_o_repetidos(self):
        libro = self.leer({"Avance: Circuitos/Eléctricos [A]": pd.DataFrame({"a": [1]}),
                           "Avance Circuitos Eléctricos [B]": pd.DataFrame({"a": [2]}),
                           "x" * 50: pd.DataFrame({"a": [3]})})
        self.assertEqual(len(libro.sheetnames), 3)
        self.assertEqual(len(set(n.lower() for n in libro.sheetnames)), 3)
        for nombre in libro.sheetnames:
            self.assertLessEqual(len(nombre), 31)
            self.assertFalse(set(nombre) & set("\\/*?:[]"))

    def test_sin_hojas_genera_un_libro_valido(self):
        self.assertEqual(self.leer({}).sheetnames, ["Resumen"])


if __name__ == "__main__":
    unittest.main()
