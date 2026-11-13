import unittest
from unittest import mock

import helpers  # noqa: F401  (configura la base temporal)

from core import rag
from core.config import TOP_K
from test_base_datos import BaseDatos

PALABRAS = ("ohm", "capacitor", "metro")


class ModeloFalso:
    # Un vector por texto: cuántas veces aparece cada palabra clave (sirve para probar sin descargar el modelo).
    def _vec(self, texto):
        return [float(texto.lower().count(p)) for p in PALABRAS]

    def get_text_embedding_batch(self, textos):
        return [self._vec(t) for t in textos]

    def get_query_embedding(self, texto):
        return self._vec(texto)


class Nodo:
    def __init__(self, texto, **meta):
        self.texto, self.metadata = texto, meta

    def get_content(self, metadata_mode=None):
        return self.texto


class TestRagEnBaseDeDatos(BaseDatos):
    def setUp(self):
        patcher = mock.patch.object(rag, "_embed_model", return_value=ModeloFalso())
        patcher.start()
        self.addCleanup(patcher.stop)
        rag.eliminar_temas([self.tema_id])

    def test_indexar_y_contar(self):
        n = rag.indexar_nodos(self.tema_id, [Nodo("la ley de ohm", documento_id=1, archivo="a.pdf", pagina=2),
                                             Nodo("un capacitor almacena energía", documento_id=1)])
        self.assertEqual((n, rag.total_chunks(self.tema_id)), (2, 2))
        self.assertEqual(rag.indexar_nodos(self.tema_id, []), 0)

    def test_el_caracter_nulo_de_algunos_pdf_se_elimina(self):
        rag.indexar_nodos(self.tema_id, [Nodo("la ley\x00 de ohm\x00", documento_id=1)])
        self.assertEqual(rag.buscar(self.tema_id, "ohm")[0]["texto"], "la ley de ohm")

    def test_buscar_devuelve_lo_relevante_con_su_fuente(self):
        rag.indexar_nodos(self.tema_id, [Nodo("la ley de ohm relaciona V e I", documento_id=7, archivo="a.pdf", pagina=3),
                                         Nodo("el capacitor guarda carga", documento_id=7, archivo="a.pdf", pagina=4)])
        r = rag.buscar(self.tema_id, "¿qué dice la ley de ohm?")
        self.assertEqual(len(r), 1)  # el del capacitor tiene similitud 0 y se descarta
        self.assertIn("ohm", r[0]["texto"])
        self.assertEqual((r[0]["archivo"], r[0]["pagina"]), ("a.pdf", 3))
        self.assertGreater(r[0]["score"], 0.9)

    def test_lo_que_no_se_parece_a_nada_no_devuelve_fragmentos(self):
        rag.indexar_nodos(self.tema_id, [Nodo("ohm ohm", documento_id=1)])
        self.assertEqual(rag.buscar(self.tema_id, "comencemos"), [])  # el caso real del bug de «comencemos»

    def test_respeta_el_maximo_de_resultados(self):
        rag.indexar_nodos(self.tema_id, [Nodo(f"ohm número {i}", documento_id=1) for i in range(TOP_K + 4)])
        self.assertEqual(len(rag.buscar(self.tema_id, "ohm")), TOP_K)

    def test_cada_tema_ve_solo_lo_suyo(self):
        rag.indexar_nodos(self.tema_id, [Nodo("ohm", documento_id=1)])
        self.assertEqual(rag.buscar(self.tema_id + 999, "ohm"), [])
        self.assertEqual(rag.chunks_aleatorios(self.tema_id + 999), [])

    def test_eliminar_un_documento_deja_los_demas(self):
        rag.indexar_nodos(self.tema_id, [Nodo("ohm uno", documento_id=1), Nodo("ohm dos", documento_id=2)])
        rag.eliminar_documento(self.tema_id, 1)
        self.assertEqual([f["texto"] for f in rag.buscar(self.tema_id, "ohm")], ["ohm dos"])
        rag.eliminar_temas([self.tema_id])
        self.assertEqual(rag.total_chunks(self.tema_id), 0)

    def test_fragmentos_al_azar(self):
        rag.indexar_nodos(self.tema_id, [Nodo(f"texto {i}", documento_id=1) for i in range(5)])
        r = rag.chunks_aleatorios(self.tema_id, 3)
        self.assertEqual(len(r), 3)
        self.assertEqual(len({f["texto"] for f in r}), 3)
        self.assertEqual(r[0]["archivo"], "")  # al azar no hay una fuente concreta
        self.assertEqual(len(rag.chunks_aleatorios(self.tema_id, 99)), 5)


if __name__ == "__main__":
    unittest.main()
