import unittest
from datetime import datetime, timedelta, timezone

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import repaso
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import (Carrera, Conversacion, Cuatrimestre, Materia, Quiz, RespuestaQuiz, Tarjeta, Tema, Unidad,
                           Universidad, Usuario)

AHORA = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


class TestReglasPuras(unittest.TestCase):
    def test_acertar_sube_de_caja_y_espacia(self):
        caja, proxima = repaso.siguiente(0, True, AHORA)
        self.assertEqual((caja, proxima), (1, AHORA + timedelta(days=3)))
        caja, proxima = repaso.siguiente(1, True, AHORA)
        self.assertEqual((caja, proxima), (2, AHORA + timedelta(days=7)))
        caja, proxima = repaso.siguiente(2, True, AHORA)
        self.assertEqual((caja, proxima), (3, AHORA + timedelta(days=14)))

    def test_acertar_en_la_ultima_caja_la_domina(self):
        self.assertEqual(repaso.siguiente(3, True, AHORA), (repaso.DOMINADA, None))
        self.assertEqual(repaso.siguiente(repaso.DOMINADA, True, AHORA), (repaso.DOMINADA, None))

    def test_fallar_regresa_al_principio_y_vuelve_manana(self):
        for caja in range(4):
            self.assertEqual(repaso.siguiente(caja, False, AHORA), (0, AHORA + timedelta(days=1)))


class TestConBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            uni = s.scalar(select(Universidad).where(Universidad.nombre == "U repaso"))
            if uni is None:
                uni = Universidad(nombre="U repaso")
                s.add(uni)
                s.flush()
                car = Carrera(nombre="C", universidad_id=uni.id)
                s.add(car)
                s.flush()
                cua = Cuatrimestre(nombre="C1", carrera_id=car.id)
                s.add(cua)
                s.flush()
                mat = Materia(nombre="Mat repaso", cuatrimestre_id=cua.id)
                s.add(mat)
                s.flush()
                un = Unidad(nombre="Un", materia_id=mat.id)
                s.add(un)
                s.flush()
                s.add(Tema(nombre="Tema repaso", unidad_id=un.id))
                s.flush()
            cls.tema = s.scalar(select(Tema.id).where(Tema.nombre == "Tema repaso"))
            for email in ("ana@rep.local", "beto@rep.local"):
                if not s.scalar(select(Usuario.id).where(Usuario.email == email)):
                    s.add(Usuario(nombre=email.split("@")[0].title(), email=email, rol="alumno",
                                  password_hash=hash_password("clave123")))
            s.flush()
            cls.ana = s.scalar(select(Usuario.id).where(Usuario.email == "ana@rep.local"))
            cls.beto = s.scalar(select(Usuario.id).where(Usuario.email == "beto@rep.local"))

    def setUp(self):
        with get_session() as s:
            s.query(Tarjeta).delete()
            s.query(RespuestaQuiz).delete()
            s.query(Quiz).delete()
            s.query(Conversacion).delete()

    def pregunta(self, alumno, correcta_idx=1, eleccion=0, hace=timedelta(days=2), texto="¿Cuánto es 1+1?"):
        """Crea una pregunta y la respuesta del alumno (por defecto fallada, hace dos días). Devuelve el id del quiz."""
        with get_session() as s:
            conv = Conversacion(alumno_id=alumno, tema_id=self.tema, titulo="Examen", tipo="examen")
            s.add(conv)
            s.flush()
            q = Quiz(conversacion_id=conv.id, tema_id=self.tema, pregunta=texto, opciones=["1", "2", "3", "4"],
                     indice_correcto=correcta_idx, explicacion="Porque sí.", dificultad=2)
            s.add(q)
            s.flush()
            s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=alumno, indice_elegido=eleccion,
                                es_correcta=eleccion == correcta_idx, fecha=datetime.now(timezone.utc) - hace))
            return q.id

    def test_un_fallo_se_vuelve_tarjeta_para_el_dia_siguiente(self):
        self.pregunta(self.ana, hace=timedelta(days=2))
        self.assertEqual(repaso.sincronizar(self.ana), 1)
        self.assertEqual(repaso.sincronizar(self.ana), 0)  # no se duplica
        pend = repaso.pendientes(self.ana)
        self.assertEqual(len(pend), 1)
        self.assertEqual((pend[0]["pregunta"], pend[0]["caja"], pend[0]["tema"]), ("¿Cuánto es 1+1?", 0, "Tema repaso"))

    def test_un_fallo_de_hoy_aun_no_toca(self):
        self.pregunta(self.ana, hace=timedelta(hours=1))
        self.assertEqual(repaso.pendientes(self.ana), [])
        self.assertEqual(repaso.contar_pendientes(self.ana), 0)

    def test_lo_que_ya_acertaste_no_es_tarjeta(self):
        qid = self.pregunta(self.ana)
        with get_session() as s:
            s.add(RespuestaQuiz(quiz_id=qid, alumno_id=self.ana, indice_elegido=1, es_correcta=True))
        self.assertEqual(repaso.sincronizar(self.ana), 0)

    def test_contar_pendientes_incluye_fallos_aun_sin_sincronizar(self):
        self.pregunta(self.ana)
        self.pregunta(self.ana, texto="otra")
        self.assertEqual(repaso.contar_pendientes(self.ana), 2)
        self.assertEqual(repaso.contar_pendientes(self.beto), 0)

    def test_responder_bien_la_espacia_y_mal_la_regresa(self):
        self.pregunta(self.ana)
        tarjeta = repaso.pendientes(self.ana)[0]
        r = repaso.responder(self.ana, tarjeta["id"], 1, AHORA)  # la correcta es la opción 1
        self.assertEqual((r["correcta"], r["caja"], r["dominada"], r["proxima"]), (True, 1, False, AHORA + timedelta(days=3)))
        self.assertEqual(r["explicacion"], "Porque sí.")
        r = repaso.responder(self.ana, tarjeta["id"], 0, AHORA)
        self.assertEqual((r["correcta"], r["caja"], r["proxima"]), (False, 0, AHORA + timedelta(days=1)))

    def test_cuatro_aciertos_seguidos_la_dominan(self):
        self.pregunta(self.ana)
        tid = repaso.pendientes(self.ana)[0]["id"]
        for _ in range(4):
            r = repaso.responder(self.ana, tid, 1, AHORA)
        self.assertTrue(r["dominada"])
        self.assertIsNone(r["proxima"])
        self.assertEqual(repaso.resumen(self.ana)["dominadas"], 1)
        self.assertEqual(repaso.pendientes(self.ana), [])

    def test_no_se_puede_responder_la_tarjeta_de_otro(self):
        self.pregunta(self.ana)
        tid = repaso.pendientes(self.ana)[0]["id"]
        self.assertIsNone(repaso.responder(self.beto, tid, 1))
        self.assertIsNone(repaso.detalle(self.beto, tid))

    def test_resumen(self):
        self.pregunta(self.ana)
        self.pregunta(self.ana, texto="b")
        tid = repaso.pendientes(self.ana)[0]["id"]
        repaso.responder(self.ana, tid, 1)  # una pasa a la caja 1: vuelve en 3 días
        r = repaso.resumen(self.ana)
        self.assertEqual((r["hoy"], r["en_repaso"], r["dominadas"]), (1, 2, 0))
        self.assertIsNotNone(r["proxima"])


if __name__ == "__main__":
    unittest.main()
