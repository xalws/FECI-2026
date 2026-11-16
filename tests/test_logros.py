import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import actividad, logros
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import Actividad, Conversacion, IntentoEjercicio, Materia, Quiz, RespuestaQuiz, Tema, Unidad, Usuario
from models.schema import Carrera, Cuatrimestre, Universidad

UTC = timezone.utc
HOY = date(2026, 11, 16)


class TestPuras(unittest.TestCase):
    def test_minutos_por_dia_usa_la_hora_local(self):
        zona = ZoneInfo("America/Ciudad_Juarez")  # UTC-7 en noviembre
        # 03:00 y 03:04 UTC del día 16 son las 20:00 y 20:04 del día 15 en Juárez
        marcas = [datetime(2026, 11, 16, 3, 0, tzinfo=UTC), datetime(2026, 11, 16, 3, 4, tzinfo=UTC)]
        r = logros.minutos_por_dia(marcas, zona)
        self.assertEqual(list(r), [date(2026, 11, 15)])
        self.assertAlmostEqual(r[date(2026, 11, 15)], 4.0)

    def test_pausas_largas_no_cuentan(self):
        marcas = [datetime(2026, 11, 16, 10, 0, tzinfo=UTC), datetime(2026, 11, 16, 10, 2, tzinfo=UTC),
                  datetime(2026, 11, 16, 15, 0, tzinfo=UTC)]
        self.assertAlmostEqual(logros.minutos_por_dia(marcas, UTC)[date(2026, 11, 16)], 2.0)

    def test_racha_maxima(self):
        dias = {HOY, HOY - timedelta(days=1), HOY - timedelta(days=2), HOY - timedelta(days=10),
                HOY - timedelta(days=11), HOY - timedelta(days=12), HOY - timedelta(days=13)}
        self.assertEqual(actividad.racha_maxima(dias), 4)
        self.assertEqual(actividad.racha_maxima(set()), 0)
        self.assertEqual(actividad.racha_maxima({HOY}), 1)

    def test_dias_con_la_meta_cumplida(self):
        self.assertEqual(logros.dias_meta_cumplida({HOY: 25, HOY - timedelta(days=1): 19.9}, 20), 1)

    def test_evaluar_marca_lo_logrado_y_limita_el_avance(self):
        datos = {"respuestas": 3, "aciertos": 12, "racha_maxima": 8, "ejercicios": 0, "mejor_ejercicio": 0,
                 "dias_meta": 2, "mejor_nivel": 3}
        por_id = {l["id"]: l for l in logros.evaluar(datos)}
        self.assertTrue(por_id["primeros_pasos"]["logrado"])
        self.assertTrue(por_id["diez_aciertos"]["logrado"])
        self.assertEqual(por_id["diez_aciertos"]["actual"], 10)             # no pasa de la meta
        self.assertFalse(por_id["cincuenta_aciertos"]["logrado"])
        self.assertEqual(por_id["cincuenta_aciertos"]["actual"], 12)
        self.assertTrue(por_id["racha_7"]["logrado"])
        self.assertFalse(por_id["racha_14"]["logrado"])
        self.assertTrue(por_id["nivel_avanzado"]["logrado"])
        self.assertFalse(por_id["experto"]["logrado"])
        self.assertEqual(len(por_id), len(logros.CATALOGO))

    def test_evaluar_sin_datos(self):
        self.assertFalse(any(l["logrado"] for l in logros.evaluar({})))

    def test_calendario(self):
        # 16/nov/2026 es lunes: la última semana empieza hoy y el resto de sus días es futuro
        filas = logros.calendario({HOY: 12.0}, HOY, semanas=3)
        self.assertEqual(len(filas), 3)
        self.assertTrue(all(len(f) == 7 for f in filas))
        self.assertEqual(filas[-1][0]["fecha"], HOY)
        self.assertEqual(filas[-1][0]["minutos"], 12.0)
        self.assertFalse(filas[-1][0]["futuro"])
        self.assertTrue(all(c["futuro"] for c in filas[-1][1:]))
        self.assertEqual(filas[0][0]["fecha"], HOY - timedelta(weeks=2))

    def test_ids_de_metas_y_catalogo_sin_repetidos(self):
        ids = [c[0] for c in logros.CATALOGO]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn(logros.META_DEFECTO, logros.METAS_MIN)


class TestConBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            uni = Universidad(nombre="U logros")
            s.add(uni)
            s.flush()
            car = Carrera(nombre="C", universidad_id=uni.id)
            s.add(car)
            s.flush()
            cua = Cuatrimestre(nombre="1", carrera_id=car.id)
            s.add(cua)
            s.flush()
            mat = Materia(nombre="M", cuatrimestre_id=cua.id)
            s.add(mat)
            s.flush()
            un = Unidad(nombre="U", materia_id=mat.id)
            s.add(un)
            s.flush()
            tema = Tema(nombre="T", unidad_id=un.id)
            s.add(tema)
            u = Usuario(nombre="Logros", email="logros@l.local", rol="alumno", password_hash=hash_password("clave123"))
            s.add(u)
            s.flush()
            conv = Conversacion(alumno_id=u.id, tema_id=tema.id, titulo="Examen", tipo="examen")
            s.add(conv)
            s.flush()
            # 10 respuestas: 8 correctas de dificultad 3 (24 XP)  -> nivel Experto
            for i in range(10):
                q = Quiz(conversacion_id=conv.id, tema_id=tema.id, pregunta=f"p{i}", opciones=["a", "b", "c", "d"],
                         indice_correcto=0, dificultad=3)
                s.add(q)
                s.flush()
                s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=u.id, indice_elegido=0, es_correcta=i < 8))
            s.add(IntentoEjercicio(alumno_id=u.id, tema_id=tema.id, enunciado="e", respuesta="r", puntaje=9))
            ahora = datetime.now(UTC)
            for dias in (0, 1, 2):
                for minuto in range(0, 30, 2):
                    s.add(Actividad(usuario_id=u.id, fecha=ahora - timedelta(days=dias, minutes=minuto)))
            cls.uid = u.id

    def test_meta_por_defecto_y_guardado(self):
        self.assertEqual(logros.meta_de(self.uid), logros.META_DEFECTO)
        logros.guardar_meta(self.uid, 45)
        self.assertEqual(logros.meta_de(self.uid), 45)
        with self.assertRaises(ValueError):
            logros.guardar_meta(self.uid, 7)
        logros.guardar_meta(self.uid, logros.META_DEFECTO)

    def test_datos_y_logros_de_un_alumno(self):
        d = logros.datos_alumno(self.uid, UTC)
        self.assertEqual(d["respuestas"], 10)
        self.assertEqual(d["aciertos"], 8)
        self.assertEqual(d["ejercicios"], 1)
        self.assertEqual(d["mejor_ejercicio"], 9)
        self.assertEqual(d["mejor_nivel"], 4)
        self.assertEqual(d["racha_maxima"], 3)
        self.assertGreaterEqual(d["racha"], 2)
        por_id = {l["id"]: l for l in logros.evaluar(d)}
        for ganado in ("primeros_pasos", "racha_3", "ejercicio_9", "nivel_avanzado", "experto"):
            self.assertTrue(por_id[ganado]["logrado"], ganado)
        for pendiente in ("cincuenta_aciertos", "racha_7", "ejercicios_5"):
            self.assertFalse(por_id[pendiente]["logrado"], pendiente)
        self.assertIn("experto", logros.ids_logrados(self.uid, UTC))

    def test_alumno_sin_actividad(self):
        with get_session() as s:
            u = Usuario(nombre="Nuevo", email="nuevo@l.local", rol="alumno", password_hash=hash_password("clave123"))
            s.add(u)
            s.flush()
            nuevo = u.id
        d = logros.datos_alumno(nuevo, UTC)
        self.assertEqual((d["respuestas"], d["racha"], d["mejor_nivel"], d["minutos_hoy"]), (0, 0, 0, 0.0))
        self.assertFalse(any(l["logrado"] for l in logros.evaluar(d)))


if __name__ == "__main__":
    unittest.main()
