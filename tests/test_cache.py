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

    def test_tabla_de_una_escritura(self):
        self.assertEqual(cache.tabla_de("INSERT INTO mensajes (a) VALUES (1)"), "mensajes")
        self.assertEqual(cache.tabla_de('  update "Temas" SET x=1'), "temas")
        self.assertEqual(cache.tabla_de("DELETE FROM clases WHERE id=1"), "clases")
        self.assertIsNone(cache.tabla_de("SELECT 1"))

    def test_el_catalogo_no_se_vacia_con_escrituras_de_otras_tablas(self):
        init_db()
        catalogo = ("universidades", "temas")
        antes = cache.version_de(catalogo)
        with get_session() as s:  # un alumno escribe un mensaje: el catálogo sigue sirviendo
            s.execute(text("UPDATE usuarios SET nombre = nombre WHERE id = -1"))
        self.assertEqual(cache.version_de(catalogo), antes)
        with get_session() as s:  # se cambia un tema: el catálogo se vuelve a leer
            s.execute(text("UPDATE temas SET nombre = nombre WHERE id = -1"))
        self.assertNotEqual(cache.version_de(catalogo), antes)

    def test_invalidar_sin_saber_que_cambio_vacia_tambien_lo_que_declaro_tablas(self):
        antes = cache.version_de(("temas",))
        cache.invalidar()
        self.assertNotEqual(cache.version_de(("temas",)), antes)

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

    def test_una_lectura_se_repite_si_se_corta_la_conexion(self):
        from sqlalchemy import exc
        llamadas = []

        @cache.solo_lectura
        def leer():
            llamadas.append(cache.modo_lectura.get())
            if len(llamadas) == 1:
                raise exc.OperationalError("SELECT 1", {}, Exception("server closed the connection unexpectedly"))
            return "ok"

        self.assertEqual(leer(), "ok")
        self.assertEqual(llamadas, [True, True])  # dos intentos, los dos sin transacción
        self.assertFalse(cache.modo_lectura.get())

    def test_otros_errores_no_se_reintentan_y_tampoco_un_segundo_corte(self):
        from sqlalchemy import exc
        llamadas = []

        @cache.solo_lectura
        def falla():
            llamadas.append(1)
            raise ValueError("dato raro")

        with self.assertRaises(ValueError):
            falla()
        self.assertEqual(len(llamadas), 1)

        @cache.solo_lectura
        def siempre_cortada():
            llamadas.append(2)
            raise exc.OperationalError("SELECT 1", {}, Exception("se cortó"))

        with self.assertRaises(exc.OperationalError):
            siempre_cortada()
        self.assertEqual(llamadas.count(2), 2)  # un reintento, no un ciclo sin fin

    def test_claves_de_los_argumentos(self):
        self.assertEqual(cache._clave(ZoneInfo("America/Ciudad_Juarez")), "America/Ciudad_Juarez")
        self.assertEqual(cache._clave(timezone.utc), "UTC")
        self.assertEqual(cache._clave([1, 2]), (1, 2))
        self.assertEqual(cache._clave({"b": 1, "a": [2]}), (("a", (2,)), ("b", 1)))


if __name__ == "__main__":
    unittest.main()
