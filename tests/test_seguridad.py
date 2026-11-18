import unittest
from datetime import datetime, timedelta, timezone

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import delete, select

from core import auth, errores, seguridad
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import ErrorApp, IntentoLogin, Usuario

CORREO = "intentos@s.local"


def borrar_intentos():
    with get_session() as s:
        s.execute(delete(IntentoLogin))


class TestLimiteDeIntentos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            if not s.scalar(select(Usuario.id).where(Usuario.email == CORREO)):
                s.add(Usuario(nombre="Intentos", email=CORREO, rol="alumno", password_hash=hash_password("buena1234")))

    def setUp(self):
        borrar_intentos()

    def test_entrar_bien_no_deja_huella(self):
        u, motivo = auth.intentar_login(CORREO, "buena1234")
        self.assertEqual(u["email"], CORREO)
        self.assertEqual(motivo, "")
        self.assertEqual(seguridad.intentos_restantes(CORREO), seguridad.MAX_FALLOS)

    def test_los_fallos_avisan_cuantos_quedan(self):
        mensajes = [auth.intentar_login(CORREO, "mala")[1] for _ in range(seguridad.MAX_FALLOS - 1)]
        self.assertEqual(mensajes[0], "Correo o contraseña incorrectos.")  # al inicio no asusta
        self.assertIn("Te quedan 2 intentos", mensajes[-2])
        self.assertIn("Te queda 1 intento", mensajes[-1])

    def test_al_llegar_al_limite_se_bloquea_aunque_acierte(self):
        for _ in range(seguridad.MAX_FALLOS):
            u, motivo = auth.intentar_login(CORREO, "mala")
        self.assertIsNone(u)
        self.assertIn("Demasiados intentos", motivo)
        self.assertGreater(seguridad.segundos_de_bloqueo(CORREO), 0)
        u, motivo = auth.intentar_login(CORREO, "buena1234")  # la contraseña buena tampoco sirve mientras dure
        self.assertIsNone(u)
        self.assertIn("Demasiados intentos", motivo)

    def test_el_bloqueo_termina_con_el_tiempo(self):
        for _ in range(seguridad.MAX_FALLOS):
            seguridad.registrar_fallo(CORREO)
        despues = datetime.now(timezone.utc) + timedelta(minutes=seguridad.VENTANA_MIN, seconds=5)
        self.assertEqual(seguridad.segundos_de_bloqueo(CORREO, despues), 0)
        self.assertEqual(seguridad.intentos_restantes(CORREO, despues), seguridad.MAX_FALLOS)

    def test_entrar_bien_borra_los_fallos_anteriores(self):
        for _ in range(3):
            auth.intentar_login(CORREO, "mala")
        auth.intentar_login(CORREO, "buena1234")
        self.assertEqual(seguridad.intentos_restantes(CORREO), seguridad.MAX_FALLOS)

    def test_correos_inexistentes_tambien_se_bloquean_y_no_se_distinguen(self):
        falso = "nadie@s.local"
        mensajes = [auth.intentar_login(falso, "x")[1] for _ in range(seguridad.MAX_FALLOS)]
        self.assertIn("Demasiados intentos", mensajes[-1])
        real = [auth.intentar_login(CORREO, "x")[1] for _ in range(seguridad.MAX_FALLOS)]
        self.assertEqual(mensajes, real)  # mismos textos, exista o no la cuenta

    def test_mayusculas_y_espacios_cuentan_como_el_mismo_correo(self):
        for _ in range(seguridad.MAX_FALLOS):
            auth.intentar_login(f"  {CORREO.upper()} ", "mala")
        self.assertGreater(seguridad.segundos_de_bloqueo(CORREO), 0)

    def test_un_correo_bloqueado_no_afecta_a_otro(self):
        for _ in range(seguridad.MAX_FALLOS):
            seguridad.registrar_fallo("otro@s.local")
        self.assertEqual(seguridad.segundos_de_bloqueo(CORREO), 0)
        self.assertIsNotNone(auth.intentar_login(CORREO, "buena1234")[0])

    def test_entrar_sin_fallos_previos_no_borra_nada(self):
        from unittest import mock
        with mock.patch.object(seguridad, "limpiar") as limpiar:
            self.assertIsNotNone(auth.intentar_login(CORREO, "buena1234")[0])
        limpiar.assert_not_called()  # una consulta menos al entrar
        auth.intentar_login(CORREO, "mala")
        with mock.patch.object(seguridad, "limpiar") as limpiar:
            auth.intentar_login(CORREO, "buena1234")
        limpiar.assert_called_once()

    def test_espera_por_fallos(self):
        ahora = datetime.now(timezone.utc)
        self.assertEqual(seguridad.espera_por_fallos(seguridad.MAX_FALLOS - 1, ahora, ahora), 0)
        self.assertEqual(seguridad.espera_por_fallos(seguridad.MAX_FALLOS, None, ahora), 0)
        self.assertEqual(seguridad.espera_por_fallos(seguridad.MAX_FALLOS, ahora, ahora), seguridad.VENTANA_MIN * 60)

    def test_texto_de_espera(self):
        self.assertEqual(seguridad.texto_de_espera(1), "1 minuto")
        self.assertEqual(seguridad.texto_de_espera(60), "1 minuto")
        self.assertEqual(seguridad.texto_de_espera(61), "2 minutos")


class TestRegistroDeErrores(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        with get_session() as s:
            s.execute(delete(ErrorApp))

    def fallo(self, mensaje="boom"):
        try:
            raise ValueError(mensaje)
        except ValueError as e:
            return e

    def test_guarda_origen_tipo_mensaje_y_traza(self):
        errores.registrar("tutor", self.fallo("algo falló"), usuario_id=7)
        df = errores.recientes()
        self.assertEqual(len(df), 1)
        fila = df.iloc[0]
        self.assertEqual((fila["origen"], fila["tipo"], fila["mensaje"], fila["usuario_id"]),
                         ("tutor", "ValueError", "algo falló", 7))
        self.assertIn("Traceback", fila["detalle"])
        self.assertIn("test_seguridad.py", fila["detalle"])

    def test_tapa_claves_y_contrasenas(self):
        e = self.fallo("no conecta a postgresql://admin:SuperSecreta@host.neon.tech/db con "
                       "api_key=gsk_abcdefghijklmnop1234 y Bearer abc.def-123 password: hunter2")
        errores.registrar("db", e)
        fila = errores.recientes().iloc[0]
        for texto in (fila["mensaje"], fila["detalle"]):
            for secreto in ("SuperSecreta", "gsk_abcdefghijklmnop1234", "abc.def-123", "hunter2"):
                self.assertNotIn(secreto, texto)
        self.assertIn("postgresql://admin:***@host.neon.tech", fila["mensaje"])

    def test_los_errores_de_la_ia_guardan_su_detalle_tecnico(self):
        from core.llm import ErrorIA
        errores.registrar("tutor", ErrorIA("Texto amable", "red", "429 Too Many Requests: cuota"))
        fila = errores.recientes().iloc[0]
        self.assertEqual(fila["mensaje"], "Texto amable")
        self.assertIn("429 Too Many Requests", fila["detalle"])

    def test_registrar_nunca_lanza(self):
        from unittest import mock
        with mock.patch("core.errores.get_session", side_effect=RuntimeError("base caída")):
            errores.registrar("tutor", self.fallo())  # no debe propagar nada

    def test_agrupa_por_tipo_y_filtra_por_origen(self):
        for _ in range(3):
            errores.registrar("tutor", self.fallo("a"))
        errores.registrar("material", self.fallo("b"))
        g = errores.por_tipo()
        self.assertEqual(list(g["origen"]), ["tutor", "material"])
        self.assertEqual(list(g["veces"]), [3, 1])
        self.assertEqual(len(errores.recientes(origen="material")), 1)

    def test_el_tope_borra_los_mas_viejos(self):
        from unittest import mock
        with mock.patch.object(errores, "MAX_FILAS", 3):
            for i in range(6):
                errores.registrar("tutor", self.fallo(f"n{i}"))
        mensajes = list(errores.recientes()["mensaje"])
        self.assertEqual(len(mensajes), 3)
        self.assertEqual(mensajes[0], "n5")  # se conservan los más nuevos

    def test_borrar_anteriores(self):
        errores.registrar("tutor", self.fallo())
        with get_session() as s:
            s.add(ErrorApp(origen="tutor", tipo="X", mensaje="viejo", fecha=datetime.now(timezone.utc) - timedelta(days=40)))
        self.assertEqual(errores.borrar_anteriores(30), 1)
        self.assertEqual(len(errores.recientes(dias=365)), 1)
        self.assertEqual(errores.borrar_anteriores(0), 1)


if __name__ == "__main__":
    unittest.main()
