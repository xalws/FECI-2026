import unittest

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import auth, cuenta
from core.db import get_session, init_db
from core.passwords import hash_password, verificar_password
from models.schema import Usuario


def hash_de(email):
    with get_session() as s:
        return s.scalar(select(Usuario.password_hash).where(Usuario.email == email))


class TestValidacion(unittest.TestCase):
    def test_reglas(self):
        self.assertIsNotNone(cuenta.validar_password("corta"))               # menos de 6
        self.assertIsNone(cuenta.validar_password("seis66"))
        self.assertIsNone(cuenta.validar_password("a" * 72))
        self.assertIsNotNone(cuenta.validar_password("a" * 73))              # pasa el límite de bcrypt
        self.assertIsNotNone(cuenta.validar_password("ñ" * 40))              # 40 caracteres pero 80 bytes
        self.assertIsNone(cuenta.validar_password("ñ" * 36))                 # 72 bytes justos


class BaseCuentas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            existentes = set(s.scalars(select(Usuario.email)))  # la base temporal se comparte entre las clases
            for email, rol, activo in (("alumno@c.local", "alumno", True), ("admin2@c.local", "admin", True),
                                       ("maestro@c.local", "maestro", True), ("baja@c.local", "alumno", False)):
                if email not in existentes:
                    s.add(Usuario(nombre=email.split("@")[0].title(), email=email, rol=rol, activo=activo,
                                  password_hash=hash_password("inicial1")))
            s.flush()
            cls.ids = {u.email: u.id for u in s.scalars(select(Usuario))}

    def setUp(self):  # cada prueba parte de la contraseña inicial
        with get_session() as s:
            for u in s.scalars(select(Usuario).where(Usuario.email.like("%@c.local"))):
                u.password_hash = hash_password("inicial1")


class TestCambiarPassword(BaseCuentas):
    def test_cambio_correcto(self):
        ok, msg = cuenta.cambiar_password(self.ids["alumno@c.local"], "inicial1", "nueva123", "nueva123")
        self.assertTrue(ok, msg)
        h = hash_de("alumno@c.local")
        self.assertTrue(verificar_password("nueva123", h))
        self.assertFalse(verificar_password("inicial1", h))  # la anterior ya no sirve

    def test_el_login_funciona_con_la_nueva(self):
        cuenta.cambiar_password(self.ids["alumno@c.local"], "inicial1", "nueva123", "nueva123")
        self.assertIsNotNone(auth.login("ALUMNO@c.local", "nueva123"))
        self.assertIsNone(auth.login("alumno@c.local", "inicial1"))

    def test_rechazos_y_no_cambia_nada(self):
        uid, antes = self.ids["alumno@c.local"], hash_de("alumno@c.local")
        casos = [("equivocada", "nueva123", "nueva123", "actual no es correcta"),
                 ("inicial1", "nueva123", "otra4567", "no coincide"),
                 ("inicial1", "corta", "corta", "al menos"),
                 ("inicial1", "inicial1", "inicial1", "distinta de la actual"),
                 ("inicial1", "a" * 80, "a" * 80, "demasiado larga")]
        for actual, nueva, conf, texto in casos:
            ok, msg = cuenta.cambiar_password(uid, actual, nueva, conf)
            self.assertFalse(ok)
            self.assertIn(texto, msg)
        self.assertEqual(hash_de("alumno@c.local"), antes)

    def test_cuenta_inactiva_o_inexistente(self):
        self.assertFalse(cuenta.cambiar_password(self.ids["baja@c.local"], "inicial1", "nueva123", "nueva123")[0])
        self.assertFalse(cuenta.cambiar_password(99999, "x", "nueva123", "nueva123")[0])


class TestRestablecer(BaseCuentas):
    def test_el_administrador_restablece(self):
        ok, msg = cuenta.restablecer_password(self.ids["admin2@c.local"], self.ids["alumno@c.local"], "temporal9")
        self.assertTrue(ok, msg)
        self.assertIn("alumno@c.local", msg)
        self.assertIsNotNone(auth.login("alumno@c.local", "temporal9"))
        self.assertIsNone(auth.login("alumno@c.local", "inicial1"))

    def test_quien_no_es_administrador_no_puede(self):
        antes = hash_de("alumno@c.local")
        for quien in ("alumno@c.local", "maestro@c.local", "baja@c.local"):
            ok, msg = cuenta.restablecer_password(self.ids[quien], self.ids["alumno@c.local"], "temporal9")
            self.assertFalse(ok)
            self.assertIn("administrador", msg)
        self.assertFalse(cuenta.restablecer_password(99999, self.ids["alumno@c.local"], "temporal9")[0])
        self.assertEqual(hash_de("alumno@c.local"), antes)

    def test_usuario_inexistente_y_contrasena_invalida(self):
        admin = self.ids["admin2@c.local"]
        self.assertFalse(cuenta.restablecer_password(admin, 99999, "temporal9")[0])
        self.assertFalse(cuenta.restablecer_password(admin, self.ids["alumno@c.local"], "x")[0])

    def test_restablecer_por_correo_desde_la_terminal(self):
        ok, _ = cuenta.restablecer_por_correo("  ADMIN2@c.local ", "terminal9")
        self.assertTrue(ok)
        self.assertIsNotNone(auth.login("admin2@c.local", "terminal9"))
        self.assertFalse(cuenta.restablecer_por_correo("nadie@c.local", "terminal9")[0])
        self.assertFalse(cuenta.restablecer_por_correo("admin2@c.local", "corta")[0])


class TestRegistroConContrasenaLarga(unittest.TestCase):
    def test_ya_no_falla_con_un_error_sino_con_un_aviso(self):
        init_db()
        ok, msg = auth.crear_usuario("Largo", "largo@c.local", "a" * 100, "alumno")
        self.assertFalse(ok)
        self.assertIn("demasiado larga", msg)


if __name__ == "__main__":
    unittest.main()
