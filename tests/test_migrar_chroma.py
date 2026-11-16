import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import helpers  # noqa: F401

from core.db import get_session
from models.schema import Fragmento
from scripts import migrar_chroma_a_bd
from test_base_datos import BaseDatos


class TestMigrarChroma(BaseDatos):
    def test_nombre_coleccion_admite_api_antigua_y_nueva(self):
        self.assertEqual(migrar_chroma_a_bd.nombre_coleccion("tema_1"), "tema_1")
        self.assertEqual(migrar_chroma_a_bd.nombre_coleccion(SimpleNamespace(name="tema_2")), "tema_2")

    def test_migra_nombres_de_coleccion_de_chromadb_actual_y_es_idempotente(self):
        nombre = f"tema_{self.tema_id}"
        coleccion = mock.Mock()
        coleccion.get.return_value = {
            "documents": ["texto migrado"],
            "metadatas": [{"documento_id": 7, "archivo": "clase.pdf", "pagina": 2}],
            "embeddings": [[0.1, 0.2]],
        }
        cliente = mock.Mock()
        cliente.list_collections.return_value = [nombre]
        cliente.get_collection.return_value = coleccion

        with tempfile.TemporaryDirectory() as directorio:
            with (mock.patch.object(migrar_chroma_a_bd, "CHROMA_PATH", directorio),
                  mock.patch.object(migrar_chroma_a_bd.chromadb, "PersistentClient", return_value=cliente),
                  contextlib.redirect_stdout(io.StringIO())):
                migrar_chroma_a_bd.main()
                migrar_chroma_a_bd.main()

        with get_session() as s:
            filas = s.query(Fragmento).filter_by(tema_id=self.tema_id).all()
        self.assertEqual(len(filas), 1)
        self.assertEqual((filas[0].texto, filas[0].documento_id, filas[0].archivo, filas[0].pagina),
                         ("texto migrado", 7, "clase.pdf", 2))
        cliente.get_collection.assert_called_once_with(name=nombre)

    def test_sin_carpeta_origen_no_inicializa_la_base_destino(self):
        with tempfile.TemporaryDirectory() as directorio:
            ruta = str(Path(directorio) / "chroma_data")
            with (mock.patch.object(migrar_chroma_a_bd, "CHROMA_PATH", ruta),
                  mock.patch.object(migrar_chroma_a_bd, "init_db") as init_db,
                  contextlib.redirect_stdout(io.StringIO())):
                migrar_chroma_a_bd.main()

        init_db.assert_not_called()


if __name__ == "__main__":
    unittest.main()
