"""Sesiones recordadas: el código vive en el navegador y la base solo guarda su huella."""
import unittest
from datetime import timedelta

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import func, select

from core import cuenta, sesion
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import Sesion, Usuario


def contar(usuario_id=None):
    with get_session() as s:
        q = select(func.count(Sesion.id))
        if usuario_id:
            q = q.where(Sesion.usuario_id == usuario_id)
        return s.scalar(q)


class TestSesion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            existentes = {u.email: u.id for u in s.scalars(select(Usuario))}
            for email in ("recuerda@s.local", "otra@s.local"):
                if email not in existentes:
                    u = Usuario(nombre=email.split("@")[0].title(), email=email, rol="alumno",
                                password_hash=hash_password("inicial1"))
                    s.add(u)
                    s.flush()
                    existentes[email] = u.id
            cls.uid, cls.otro = existentes["recuerda@s.local"], existentes["otra@s.local"]

    def setUp(self):
        with get_session() as s:
            s.query(Sesion).delete()
            u = s.get(Usuario, self.uid)
            u.activo, u.password_hash = True, hash_password("inicial1")

    def test_el_codigo_abre_la_sesion_y_la_base_no_lo_guarda(self):
        token = sesion.crear(self.uid)
        self.assertEqual(sesion.validar(token)["id"], self.uid)
        self.assertEqual(sesion.validar(token)["rol"], "alumno")
        with get_session() as s:
            guardado = s.scalar(select(Sesion.token_hash))
        self.assertNotEqual(guardado, token)
        self.assertNotIn(token, guardado)
        self.assertEqual(len(guardado), 64)  # SHA-256 en hexadecimal

    def test_codigos_invalidos(self):
        for malo in (None, "", "no-existe", "x" * 500):
            self.assertIsNone(sesion.validar(malo))

    def test_cada_sesion_tiene_su_propio_codigo(self):
        self.assertNotEqual(sesion.crear(self.uid), sesion.crear(self.uid))
        self.assertEqual(contar(self.uid), 2)

    def test_revocar_deja_de_servir(self):
        token = sesion.crear(self.uid)
        sesion.revocar(token)
        self.assertIsNone(sesion.validar(token))
        sesion.revocar(None)  # no falla

    def test_vencida_no_sirve_y_se_limpia(self):
        token = sesion.crear(self.uid, dias=-1)
        self.assertIsNone(sesion.validar(token))
        sesion.crear(self.uid)  # al crear otra se borran las vencidas
        self.assertEqual(contar(self.uid), 1)

    def test_cuenta_desactivada_no_entra(self):
        token = sesion.crear(self.uid)
        with get_session() as s:
            s.get(Usuario, self.uid).activo = False
        self.assertIsNone(sesion.validar(token))

    def test_limite_de_sesiones_por_usuario(self):
        for _ in range(sesion.MAX_SESIONES_POR_USUARIO + 4):
            sesion.crear(self.uid)
        self.assertEqual(contar(self.uid), sesion.MAX_SESIONES_POR_USUARIO)

    def test_revocar_todas_respeta_a_las_demas_cuentas_y_conserva_una(self):
        actual, otra = sesion.crear(self.uid), sesion.crear(self.uid)
        ajena = sesion.crear(self.otro)
        sesion.revocar_todas(self.uid, conservar=actual)
        self.assertIsNotNone(sesion.validar(actual))
        self.assertIsNone(sesion.validar(otra))
        self.assertIsNotNone(sesion.validar(ajena))
        sesion.revocar_todas(self.uid)
        self.assertIsNone(sesion.validar(actual))
        self.assertIsNotNone(sesion.validar(ajena))

    def test_cambiar_la_contrasena_cierra_las_otras_sesiones(self):
        aqui, alla = sesion.crear(self.uid), sesion.crear(self.uid)
        ok, _ = cuenta.cambiar_password(self.uid, "inicial1", "nueva123", "nueva123", conservar_token=aqui)
        self.assertTrue(ok)
        self.assertIsNotNone(sesion.validar(aqui))
        self.assertIsNone(sesion.validar(alla))

    def test_contrasena_incorrecta_no_cierra_nada(self):
        token = sesion.crear(self.uid)
        ok, _ = cuenta.cambiar_password(self.uid, "equivocada", "nueva123", "nueva123")
        self.assertFalse(ok)
        self.assertIsNotNone(sesion.validar(token))

    def test_restablecer_por_correo_cierra_todas(self):
        token = sesion.crear(self.uid)
        ok, _ = cuenta.restablecer_por_correo("recuerda@s.local", "otraclave1")
        self.assertTrue(ok)
        self.assertIsNone(sesion.validar(token))


if __name__ == "__main__":
    unittest.main()
