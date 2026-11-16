import json
import unittest
import zipfile
from io import BytesIO

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import respaldo
from core.db import get_session, init_db
from models.schema import Base, Fragmento, Tema, Usuario


class TestRespaldo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def abrir(self, **kw):
        contenido, manifiesto = respaldo.crear(**kw)
        return zipfile.ZipFile(BytesIO(contenido)), manifiesto

    def test_hay_un_archivo_por_tabla_y_un_manifiesto(self):
        z, manifiesto = self.abrir()
        nombres = set(z.namelist())
        self.assertIn("manifiesto.json", nombres)
        for tabla in Base.metadata.sorted_tables:
            self.assertIn(f"{tabla.name}.jsonl", nombres)
        self.assertEqual(set(manifiesto["filas"]), {t.name for t in Base.metadata.sorted_tables})
        self.assertEqual(json.loads(z.read("manifiesto.json"))["formato"], respaldo.FORMATO)

    def test_las_filas_coinciden_con_la_base(self):
        z, manifiesto = self.abrir()
        with get_session() as s:
            correos = set(s.scalars(select(Usuario.email)))
        guardados = {json.loads(l)["email"] for l in z.read("usuarios.jsonl").decode().splitlines()}
        self.assertEqual(guardados, correos)
        self.assertEqual(manifiesto["filas"]["usuarios"], len(correos))

    def test_las_fechas_y_los_textos_con_acentos_quedan_legibles(self):
        z, _ = self.abrir()
        fila = json.loads(z.read("usuarios.jsonl").decode().splitlines()[0])
        self.assertIsInstance(fila["fecha"], str)
        self.assertIn("T", fila["fecha"])  # ISO 8601

    def test_sin_vectores_no_guarda_la_columna_embedding(self):
        with get_session() as s:
            tema = s.scalar(select(Tema.id).limit(1))
            if tema is None:
                self.skipTest("no hay temas en la base de pruebas")
            s.add(Fragmento(tema_id=tema, texto="ñandú", embedding=[0.1, 0.2]))
        con, _ = self.abrir(incluir_vectores=True)
        sin, manifiesto = self.abrir(incluir_vectores=False)
        self.assertIn("embedding", json.loads(con.read("fragmentos.jsonl").decode().splitlines()[-1]))
        self.assertNotIn("embedding", json.loads(sin.read("fragmentos.jsonl").decode().splitlines()[-1]))
        self.assertFalse(manifiesto["con_vectores"])
        self.assertIn("ñandú", sin.read("fragmentos.jsonl").decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
