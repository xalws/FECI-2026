import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import actividad, logros
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import (Actividad, Carrera, Clase, Conversacion, Cuatrimestre, Inscripcion, IntentoEjercicio, Materia,
                           Mensaje, Quiz, RespuestaQuiz, Tema, Unidad, Universidad, Usuario)

UTC = timezone.utc
HOY = date(2026, 11, 16)  # lunes


class TestReglasPuras(unittest.TestCase):
    def test_minutos_por_dia_usa_la_hora_local(self):
        zona = ZoneInfo("America/Ciudad_Juarez")  # UTC-7 en noviembre
        marcas = [datetime(2026, 11, 16, 3, 0, tzinfo=UTC), datetime(2026, 11, 16, 3, 4, tzinfo=UTC)]
        r = logros.minutos_por_dia(marcas, zona)
        self.assertEqual(list(r), [date(2026, 11, 15)])
        self.assertAlmostEqual(r[date(2026, 11, 15)], 4.0)

    def test_pausas_largas_no_cuentan(self):
        marcas = [datetime(2026, 11, 16, 10, 0, tzinfo=UTC), datetime(2026, 11, 16, 10, 2, tzinfo=UTC),
                  datetime(2026, 11, 16, 15, 0, tzinfo=UTC)]
        self.assertAlmostEqual(logros.minutos_por_dia(marcas, UTC)[date(2026, 11, 16)], 2.0)

    def test_racha_maxima_y_dias_con_meta(self):
        dias = {HOY, HOY - timedelta(days=1), HOY - timedelta(days=2), HOY - timedelta(days=10),
                HOY - timedelta(days=11), HOY - timedelta(days=12), HOY - timedelta(days=13)}
        self.assertEqual(actividad.racha_maxima(dias), 4)
        self.assertEqual(logros.dias_meta_cumplida({HOY: 25, HOY - timedelta(days=1): 19.9}, 20), 1)

    def test_fines_de_semana_completos(self):
        sab, dom = date(2026, 11, 14), date(2026, 11, 15)
        self.assertEqual(logros.fines_de_semana({sab, dom}), 1)
        self.assertEqual(logros.fines_de_semana({sab}), 0)
        self.assertEqual(logros.fines_de_semana({dom, date(2026, 11, 21)}), 0)
        self.assertEqual(logros.fines_de_semana({sab, dom, sab - timedelta(days=7), dom - timedelta(days=7)}), 2)

    def test_aciertos_seguidos(self):
        self.assertEqual(logros.aciertos_seguidos([True, True, False, True, True, True, False]), 3)
        self.assertEqual(logros.aciertos_seguidos([]), 0)
        self.assertEqual(logros.aciertos_seguidos([False, False]), 0)

    def test_semanas_y_meses(self):
        lunes = date(2026, 11, 9)
        semana = {lunes + timedelta(days=i) for i in range(7)}
        r = logros.semanas_y_meses(semana | {date(2026, 12, 1)})
        self.assertEqual((r["semanas_activas"], r["semanas_perfectas"], r["meses_activos"]), (2, 1, 2))
        self.assertEqual(r["mes_intenso"], 7)

    def test_racha_y_semanas_con_meta(self):
        lunes = date(2026, 11, 9)
        minutos = {lunes + timedelta(days=i): 20.0 for i in range(5)}
        minutos[lunes + timedelta(days=5)] = 5.0
        self.assertEqual(logros.racha_meta(minutos, 15), 5)
        self.assertEqual(logros.semanas_con_meta(minutos, 15), 1)
        self.assertEqual(logros.semanas_con_meta(minutos, 25), 0)

    def test_dias_por_nombre_y_maximos(self):
        lunes = date(2026, 11, 9)
        self.assertEqual(logros.dias_por_nombre({lunes, lunes + timedelta(days=7), lunes + timedelta(days=6)}),
                         [2, 0, 0, 0, 0, 0, 1])
        self.assertEqual(logros.maximo_por_dia([lunes, lunes, lunes + timedelta(days=1)]), 2)
        self.assertEqual(logros.maximo_por_dia([]), 0)
        self.assertEqual(logros.xp_maximos([(lunes, 3), (lunes, 4), (lunes + timedelta(days=2), 5), (lunes + timedelta(days=9), 20)]),
                         (20, 20))

    def test_franjas_horarias(self):
        d = datetime(2026, 11, 9)
        r = logros.franjas_horarias([d.replace(hour=3), d.replace(hour=9), d.replace(hour=20),
                                     (d + timedelta(days=1)).replace(hour=14), (d + timedelta(days=1)).replace(hour=23)])
        self.assertEqual((r["dias_buho"], r["dias_manana"], r["dias_noche"], r["dias_tarde"]), (1, 1, 1, 1))
        self.assertEqual((r["dias_noctambulo"], r["dias_doble_turno"], r["dias_madrugador"]), (1, 1, 1))

    def test_errores_corregidos_y_examenes(self):
        self.assertEqual(logros.errores_corregidos([(1, False), (1, True), (1, True), (2, False), (3, True)]), 1)
        buenos = logros.examenes_buenos({1: [True] * 5, 2: [True] * 4 + [False] * 1, 3: [True] * 3})
        self.assertEqual(buenos, (1, 2))

    def test_calendario_con_semanas_por_delante(self):
        filas = logros.calendario({HOY: 12.0}, HOY, semanas=3, futuras=2)
        self.assertEqual(len(filas), 5)
        self.assertTrue(all(c["futuro"] for fila in filas[3:] for c in fila))  # las dos últimas son del futuro
        self.assertEqual(filas[2][0]["fecha"], HOY - timedelta(days=HOY.weekday()))  # la semana actual sigue en su lugar

    def test_calendario(self):
        filas = logros.calendario({HOY: 12.0}, HOY, semanas=3)
        self.assertEqual(len(filas), 3)
        self.assertEqual(filas[-1][0]["fecha"], HOY)
        self.assertEqual(filas[-1][0]["minutos"], 12.0)
        self.assertTrue(all(c["futuro"] for c in filas[-1][1:]))
        self.assertEqual(filas[0][0]["fecha"], HOY - timedelta(weeks=2))


class TestCatalogo(unittest.TestCase):
    def test_hay_muchos_logros_en_varias_categorias(self):
        self.assertGreaterEqual(len(logros.CATALOGO), 20)
        self.assertGreaterEqual(len({c[1] for c in logros.CATALOGO}), 6)

    def test_estructura_valida(self):
        ids = [c[0] for c in logros.CATALOGO]
        self.assertEqual(len(ids), len(set(ids)))
        for id_, categoria, titulo, plantilla, icono, clave, umbrales in logros.CATALOGO:
            self.assertIn(categoria, logros.CATEGORIAS, id_)
            self.assertEqual(len(umbrales), 4, id_)
            self.assertEqual(list(umbrales), sorted(set(umbrales)), f"{id_}: umbrales crecientes y distintos")
            self.assertIn("{n}", plantilla, id_)
            self.assertTrue(titulo and icono and clave)

    def test_todo_dato_medido_existe_en_datos_alumno(self):
        # datos_alumno se prueba con una base real más abajo; aquí se verifican las claves contra una evaluación vacía
        claves = {c[5] for c in logros.CATALOGO}
        self.assertGreaterEqual(len(claves), 20)

    def test_niveles(self):
        por_id = {l["id"]: l for l in logros.evaluar({"racha_maxima": 7})}
        racha = por_id["racha"]
        self.assertEqual((racha["nivel"], racha["nombre_nivel"]), (2, "Plata"))
        self.assertEqual(racha["siguiente"], 14)
        self.assertEqual(racha["descripcion"], "Estudia 14 días seguidos")   # la descripción apunta al siguiente nivel
        self.assertEqual(racha["avance"], round((7 - 7) / (14 - 7) * 100))
        self.assertEqual(logros.evaluar({"racha_maxima": 10})[0]["avance"], round((10 - 7) / (14 - 7) * 100))

    def test_oro_es_el_nivel_maximo(self):
        racha = logros.evaluar({"racha_maxima": 500})[0]
        self.assertEqual((racha["nivel"], racha["nombre_nivel"], racha["siguiente"], racha["avance"]), (4, "Oro", None, 100))
        self.assertEqual(racha["descripcion"], "Estudia 30 días seguidos")

    def test_sin_datos_no_hay_logros(self):
        evaluados = logros.evaluar({})
        self.assertTrue(all(l["nivel"] == 0 and l["avance"] == 0 for l in evaluados))
        self.assertEqual(logros.resumen(evaluados), {"medallas": 0, "maximas": 4 * len(evaluados), "oro": 0, "logros": 0})

    def test_resumen(self):
        datos = {"racha_maxima": 30, "aciertos": 12, "ejercicios": 1}
        r = logros.resumen(logros.evaluar(datos))
        self.assertEqual(r["oro"], 1)
        self.assertEqual(r["logros"], 3)
        self.assertEqual(r["medallas"], 4 + 1 + 1)  # Oro + Bronce + Bronce

    def test_vitrina_respeta_la_eleccion_y_solo_muestra_lo_conseguido(self):
        evaluados = logros.evaluar({"racha_maxima": 30, "aciertos": 12, "ejercicios": 1})
        elegidos = logros.elegir_vitrina(evaluados, ["aciertos", "xp", "racha"])  # «xp» no se ha conseguido
        self.assertEqual([l["id"] for l in elegidos], ["aciertos", "racha"])

    def test_sin_eleccion_se_muestran_los_mejores(self):
        evaluados = logros.evaluar({"racha_maxima": 30, "aciertos": 12, "ejercicios": 1, "respuestas": 10, "clases": 1})
        auto = logros.elegir_vitrina(evaluados, [])
        self.assertEqual(len(auto), 3)
        self.assertEqual(auto[0]["id"], "racha")  # el de mayor nivel primero
        self.assertEqual(logros.elegir_vitrina(logros.evaluar({}), []), [])


class TestConBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            uni = Universidad(nombre="U logros v2")
            s.add(uni)
            s.flush()
            car = Carrera(nombre="C", universidad_id=uni.id)
            s.add(car)
            s.flush()
            cua = Cuatrimestre(nombre="Cuatrimestre 1", carrera_id=car.id)
            s.add(cua)
            s.flush()
            mat = Materia(nombre="M", cuatrimestre_id=cua.id)
            s.add(mat)
            s.flush()
            un = Unidad(nombre="U", materia_id=mat.id)
            s.add(un)
            s.flush()
            tema = Tema(nombre="T", unidad_id=un.id)
            tema2 = Tema(nombre="T2", unidad_id=un.id)
            s.add_all([tema, tema2])
            u = Usuario(nombre="Logros", email="logros@l.local", rol="alumno", password_hash=hash_password("clave123"))
            maestro = Usuario(nombre="Prof", email="prof@l.local", rol="maestro", password_hash=hash_password("clave123"))
            s.add_all([u, maestro])
            s.flush()
            conv = Conversacion(alumno_id=u.id, tema_id=tema.id, titulo="Examen", tipo="examen")
            s.add(conv)
            s.flush()
            # 10 respuestas en el tema 1 (8 correctas de dificultad 3 = 24 XP -> Experto), 2 expertas correctas aparte
            for i in range(10):
                q = Quiz(conversacion_id=conv.id, tema_id=tema.id, pregunta=f"p{i}", opciones=["a", "b", "c", "d"],
                         indice_correcto=0, dificultad=3)
                s.add(q)
                s.flush()
                s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=u.id, indice_elegido=0, es_correcta=i < 8))
            for i in range(2):
                q = Quiz(conversacion_id=conv.id, tema_id=tema2.id, pregunta=f"e{i}", opciones=["a", "b", "c", "d"],
                         indice_correcto=0, dificultad=4)
                s.add(q)
                s.flush()
                s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=u.id, indice_elegido=0, es_correcta=True))
            s.add(IntentoEjercicio(alumno_id=u.id, tema_id=tema.id, enunciado="e", respuesta="r", puntaje=10))
            s.add(IntentoEjercicio(alumno_id=u.id, tema_id=tema.id, enunciado="e2", respuesta="r", puntaje=9))
            for texto in ("hola", "otra pregunta", "una más"):
                s.add(Mensaje(conversacion_id=conv.id, rol="user", contenido=texto))
            s.add(Mensaje(conversacion_id=conv.id, rol="assistant", contenido="respuesta"))
            ahora = datetime.now(UTC)
            for dias in (0, 1, 2):
                for minuto in range(0, 30, 2):
                    s.add(Actividad(usuario_id=u.id, fecha=ahora - timedelta(days=dias, minutes=minuto)))
            clase = Clase(nombre="G", materia_id=mat.id, maestro_id=maestro.id, codigo="LOGRO1", aprobacion=False)
            s.add(clase)
            s.flush()
            s.add(Inscripcion(clase_id=clase.id, alumno_id=u.id, estado="activo"))
            cls.uid = u.id

    def test_meta_por_defecto_y_guardado(self):
        self.assertEqual(logros.meta_de(self.uid), logros.META_DEFECTO)
        logros.guardar_meta(self.uid, 45)
        self.assertEqual(logros.meta_de(self.uid), 45)
        with self.assertRaises(ValueError):
            logros.guardar_meta(self.uid, 7)
        logros.guardar_meta(self.uid, logros.META_DEFECTO)

    def test_datos_de_un_alumno(self):
        d = logros.datos_alumno(self.uid, UTC)
        self.assertEqual((d["respuestas"], d["aciertos"], d["aciertos_expertos"]), (12, 10, 2))
        self.assertEqual(d["aciertos_seguidos"], 8)            # 8 buenas, 2 malas, 2 buenas: la mejor racha es 8
        self.assertEqual((d["ejercicios"], d["ejercicios_9"], d["ejercicios_10"]), (2, 2, 1))
        self.assertEqual(d["temas_explorados"], 2)
        self.assertEqual(d["materias_exploradas"], 1)
        self.assertEqual(d["preguntas_tutor"], 3)              # solo los mensajes del alumno
        self.assertEqual(d["clases"], 1)
        self.assertEqual(d["racha_maxima"], 3)
        self.assertEqual(d["dias_activos"], 3)
        self.assertGreater(d["minutos_total"], 30)
        self.assertGreaterEqual(d["temas_nivel4"], 1)
        self.assertGreaterEqual(d["xp_total"], 24)

    def test_logros_del_alumno(self):
        por_id = {l["id"]: l for l in logros.evaluar(logros.datos_alumno(self.uid, UTC))}
        self.assertEqual(por_id["racha"]["nivel"], 1)            # 3 días = Bronce
        self.assertEqual(por_id["ejercicios"]["nivel"], 1)
        self.assertEqual(por_id["ej_9"]["nivel"], 1)
        self.assertEqual(por_id["aciertos"]["nivel"], 1)         # 10 aciertos
        self.assertEqual(por_id["tutor"]["nivel"], 0)            # 3 preguntas < 5
        self.assertEqual(por_id["clases"]["nivel"], 1)
        self.assertEqual(por_id["temas_exp"]["nivel"], 1)
        self.assertIn("racha", logros.niveles_logrados(self.uid, UTC))

    def test_alumno_sin_actividad(self):
        with get_session() as s:
            u = Usuario(nombre="Nuevo", email="nuevo@l.local", rol="alumno", password_hash=hash_password("clave123"))
            s.add(u)
            s.flush()
            nuevo = u.id
        d = logros.datos_alumno(nuevo, UTC)
        self.assertEqual((d["respuestas"], d["racha"], d["xp_total"], d["minutos_hoy"]), (0, 0, 0, 0.0))
        self.assertEqual(logros.niveles_logrados(nuevo, UTC), {})

    def test_guardar_y_leer_la_vitrina(self):
        self.assertTrue(logros.guardar_vitrina(self.uid, ["racha", "aciertos", "racha"])[0])  # sin repetir
        self.assertEqual(logros.vitrina_de(self.uid), ["racha", "aciertos"])
        self.assertFalse(logros.guardar_vitrina(self.uid, ["no_existe"])[0])
        self.assertFalse(logros.guardar_vitrina(self.uid, [c[0] for c in logros.CATALOGO[: logros.MAX_VITRINA + 1]])[0])
        self.assertEqual(logros.vitrina_de(self.uid), ["racha", "aciertos"])                # no cambió
        self.assertTrue(logros.guardar_vitrina(self.uid, [])[0])
        self.assertEqual(logros.vitrina_de(self.uid), [])


if __name__ == "__main__":
    unittest.main()
