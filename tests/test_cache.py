import unittest
from datetime import timezone
from zoneinfo import ZoneInfo

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import text

from core import cache
from core.db import engine, get_session, init_db


class TestCache(unittest.TestCase):
    def test_que_cuenta_como_escritura(self):
        for sql in ("INSERT INTO mensajes (a) VALUES (1)", "  update usuarios SET x=1", "DELETE FROM clases"):
            self.assertTrue(cache.es_escritura(sql), sql)
        for sql in ("SELECT 1", "INSERT INTO actividad (usuario_id) VALUES (1)", "INSERT INTO sesiones (a) VALUES (1)",
                    "UPDATE sesiones SET x=1", "DELETE FROM sesiones WHERE expira < 1"):
            self.assertFalse(cache.es_escritura(sql), sql)

    def test_una_escritura_confirmada_sube_la_version_y_una_lectura_no(self):
        init_db()
        antes = cache.version()
        with get_session() as s:
            s.execute(text("SELECT 1"))
        self.assertEqual(cache.version(), antes)
        with get_session() as s:
            s.execute(text("UPDATE usuarios SET nombre = nombre WHERE id = -1"))
        self.assertEqual(cache.version(), antes + 1)

    def test_una_escritura_deshecha_no_sube_la_version(self):
        init_db()
        antes = cache.version()
        with self.assertRaises(RuntimeError):
            with get_session() as s:
                s.execute(text("UPDATE usuarios SET nombre = nombre WHERE id = -1"))
                raise RuntimeError("falla antes de confirmar")
        self.assertEqual(cache.version(), antes)

    def test_la_actividad_no_vacia_la_cache(self):
        init_db()
        antes = cache.version()
        with get_session() as s:
            s.execute(text("INSERT INTO actividad (usuario_id, fecha) VALUES (-1, CURRENT_TIMESTAMP)"))
            s.rollback()
        self.assertEqual(cache.version(), antes)

    def test_fuera_de_streamlit_siempre_se_ejecuta_la_funcion(self):
        llamadas = []

        @cache.memo
        def leer(x):
            llamadas.append(x)
            return x * 2

        self.assertEqual((leer(2), leer(2)), (4, 4))
        self.assertEqual(llamadas, [2, 2])  # sin caché en pruebas y scripts
        self.assertEqual(leer.sin_cache(3), 6)

    def test_las_lecturas_guardadas_usan_conexion_sin_transaccion(self):
        init_db()
        vistos = []

        @cache.memo
        def leer():
            with get_session() as s:
                vistos.append(s.get_bind().get_execution_options().get("isolation_level"))
                return s.execute(text("SELECT COUNT(*) FROM usuarios")).scalar()

        self.assertGreaterEqual(leer(), 1)
        with get_session() as s:  # fuera de una lectura guardada, la sesión normal
            self.assertIsNone(s.get_bind().get_execution_options().get("isolation_level"))
        self.assertEqual(vistos, ["AUTOCOMMIT"])
        self.assertFalse(cache.modo_lectura.get())

    def test_claves_de_los_argumentos(self):
        self.assertEqual(cache._clave(ZoneInfo("America/Ciudad_Juarez")), "America/Ciudad_Juarez")
        self.assertEqual(cache._clave(timezone.utc), "UTC")
        self.assertEqual(cache._clave([1, 2]), (1, 2))
        self.assertEqual(cache._clave({"b": 1, "a": [2]}), (("a", (2,)), ("b", 1)))


if __name__ == "__main__":
    unittest.main()
