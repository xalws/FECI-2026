import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import clases, tareas
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import (Asignacion, Aviso, Carrera, Clase, Conversacion, Cuatrimestre, Inscripcion, IntentoEjercicio, Materia,
                           Quiz, RespuestaQuiz, Tarea, Tema, Unidad, Universidad, Usuario)

AHORA = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
ZONA = ZoneInfo("America/Ciudad_Juarez")


class TestReglasPuras(unittest.TestCase):
    def test_descripcion(self):
        self.assertEqual(tareas.descripcion("preguntas", 1), "Responder 1 pregunta de examen")
        self.assertEqual(tareas.descripcion("preguntas", 10), "Responder 10 preguntas de examen")
        self.assertEqual(tareas.descripcion("ejercicios", 2), "Resolver 2 ejercicios")
        self.assertEqual(tareas.descripcion("nivel", 2), "Llegar al nivel Intermedio")

    def test_estado(self):
        limite = AHORA + timedelta(days=5)
        self.assertEqual(tareas.estado_de(10, 10, limite, AHORA), "hecha")
        self.assertEqual(tareas.estado_de(12, 10, limite, AHORA), "hecha")
        self.assertEqual(tareas.estado_de(3, 10, limite, AHORA), "pendiente")
        self.assertEqual(tareas.estado_de(3, 10, AHORA + timedelta(days=2), AHORA), "pronto")
        self.assertEqual(tareas.estado_de(3, 10, AHORA - timedelta(minutes=1), AHORA), "vencida")
        self.assertEqual(tareas.estado_de(10, 10, AHORA - timedelta(days=3), AHORA), "hecha")  # cumplida a tiempo o tarde

    def test_estado_acepta_fechas_sin_zona(self):  # SQLite las devuelve así
        self.assertEqual(tareas.estado_de(0, 1, (AHORA + timedelta(days=9)).replace(tzinfo=None), AHORA), "pendiente")

    def test_texto_del_plazo(self):
        def en(dias, horas=0):
            return tareas.texto_plazo(AHORA + timedelta(days=dias, hours=horas), AHORA, ZONA)
        self.assertEqual(en(0, 2), "vence hoy")
        self.assertEqual(en(1), "vence mañana")
        self.assertEqual(en(5), "vence en 5 días")
        self.assertEqual(en(-1), "venció ayer")
        self.assertEqual(en(-4), "venció hace 4 días")


class TestConBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            uni = s.scalar(select(Universidad).where(Universidad.nombre == "U tareas"))
            if uni is None:
                uni = Universidad(nombre="U tareas")
                s.add(uni)
                s.flush()
                car = Carrera(nombre="C", universidad_id=uni.id)
                s.add(car)
                s.flush()
                cua = Cuatrimestre(nombre="Cuatrimestre 1", carrera_id=car.id)
                s.add(cua)
                s.flush()
                for nombre in ("Mat A tareas", "Mat B tareas"):
                    m = Materia(nombre=nombre, cuatrimestre_id=cua.id)
                    s.add(m)
                    s.flush()
                    u = Unidad(nombre=f"Unidad {nombre}", materia_id=m.id)
                    s.add(u)
                    s.flush()
                    s.add(Tema(nombre=f"Tema {nombre}", unidad_id=u.id))
                s.flush()
            cls.mat_a = s.scalar(select(Materia.id).where(Materia.nombre == "Mat A tareas"))
            cls.mat_b = s.scalar(select(Materia.id).where(Materia.nombre == "Mat B tareas"))
            cls.tema_a = s.scalar(select(Tema.id).where(Tema.nombre == "Tema Mat A tareas"))
            cls.tema_b = s.scalar(select(Tema.id).where(Tema.nombre == "Tema Mat B tareas"))

            def usuario(email, rol):
                u = s.scalar(select(Usuario).where(Usuario.email == email))
                if u is None:
                    u = Usuario(nombre=email.split("@")[0].title(), email=email, rol=rol, password_hash=hash_password("clave123"))
                    s.add(u)
                    s.flush()
                return u.id
            cls.prof = usuario("prof@tar.local", "maestro")
            cls.otro_prof = usuario("otro@tar.local", "maestro")
            cls.ana = usuario("ana@tar.local", "alumno")
            cls.beto = usuario("beto@tar.local", "alumno")
            cls.carla = usuario("carla@tar.local", "alumno")
            if not s.scalar(select(Asignacion.id).where(Asignacion.maestro_id == cls.prof, Asignacion.materia_id == cls.mat_a)):
                s.add(Asignacion(maestro_id=cls.prof, materia_id=cls.mat_a))

    def setUp(self):
        with get_session() as s:
            s.query(Tarea).delete()
            s.query(Aviso).delete()
            s.query(Inscripcion).delete()
            s.query(Clase).delete()
            s.query(RespuestaQuiz).delete()
            s.query(IntentoEjercicio).delete()
        ok, msg, self.clase = clases.crear_clase(self.prof, self.mat_a, "Grupo T", aprobacion=False)
        self.assertTrue(ok, msg)
        with get_session() as s:
            codigo = s.get(Clase, self.clase).codigo
        for alumno in (self.ana, self.beto):
            self.assertTrue(clases.unirse(alumno, codigo)[0])

    def asignar(self, tipo="preguntas", meta=3, dias=5, tema=None, nota=""):
        ok, msg, tid = tareas.crear(self.prof, self.clase, tema or self.tema_a, tipo, meta,
                                    datetime.now(timezone.utc) + timedelta(days=dias), nota)
        self.assertTrue(ok, msg)
        return tid

    def responder(self, alumno, n, tema=None, dificultad=2, correcta=True, hace=None):
        with get_session() as s:
            conv = Conversacion(alumno_id=alumno, tema_id=tema or self.tema_a, titulo="x", tipo="examen")
            s.add(conv)
            s.flush()
            for _ in range(n):
                q = Quiz(conversacion_id=conv.id, tema_id=tema or self.tema_a, pregunta="?", opciones=["a", "b"],
                         indice_correcto=0, dificultad=dificultad)
                s.add(q)
                s.flush()
                r = RespuestaQuiz(quiz_id=q.id, alumno_id=alumno, indice_elegido=0, es_correcta=correcta)
                if hace:
                    r.fecha = datetime.now(timezone.utc) - hace
                s.add(r)

    # ---- crear ----
    def test_el_maestro_asigna_una_tarea(self):
        tid = self.asignar(nota="Con calma")
        with get_session() as s:
            t = s.get(Tarea, tid)
            self.assertEqual((t.clase_id, t.tema_id, t.tipo, t.meta, t.instrucciones, t.autor_id),
                             (self.clase, self.tema_a, "preguntas", 3, "Con calma", self.prof))

    def test_validaciones_al_crear(self):
        futuro = datetime.now(timezone.utc) + timedelta(days=3)
        casos = [
            (self.prof, self.tema_b, "preguntas", 3, futuro, "tema de otra materia"),
            (self.prof, self.tema_a, "baile", 3, futuro, "tipo inválido"),
            (self.prof, self.tema_a, "preguntas", 0, futuro, "meta baja"),
            (self.prof, self.tema_a, "preguntas", 51, futuro, "meta alta"),
            (self.prof, self.tema_a, "nivel", 5, futuro, "nivel inexistente"),
            (self.prof, self.tema_a, "preguntas", 3, datetime.now(timezone.utc) - timedelta(hours=1), "fecha pasada"),
            (self.otro_prof, self.tema_a, "preguntas", 3, futuro, "maestro ajeno a la clase"),
            (self.ana, self.tema_a, "preguntas", 3, futuro, "un alumno no asigna"),
        ]
        for usuario, tema, tipo, meta, fecha, que in casos:
            ok, _, tid = tareas.crear(usuario, self.clase, tema, tipo, meta, fecha)
            self.assertFalse(ok, que)
            self.assertIsNone(tid, que)
        self.assertFalse(tareas.crear(self.prof, self.clase, self.tema_a, "preguntas", 3, futuro, "x" * 301)[0])

    # ---- avance ----
    def test_preguntas_solo_cuentan_las_respondidas_despues_de_asignar(self):
        self.responder(self.ana, 5, hace=timedelta(days=2))  # antes de la tarea: no cuentan
        self.asignar("preguntas", 3)
        self.responder(self.ana, 2)
        self.responder(self.beto, 3)
        por_alumno = {t["alumno_id"]: t for t in tareas.detalle(self.prof, self.asignar_primera())}
        self.assertEqual((por_alumno[self.ana]["avance"], por_alumno[self.ana]["hecha"]), (2, False))
        self.assertEqual((por_alumno[self.beto]["avance"], por_alumno[self.beto]["hecha"]), (3, True))

    def asignar_primera(self):
        with get_session() as s:
            return s.scalar(select(Tarea.id).order_by(Tarea.id))

    def test_ejercicios(self):
        tid = self.asignar("ejercicios", 2)
        with get_session() as s:
            for _ in range(2):
                s.add(IntentoEjercicio(alumno_id=self.ana, tema_id=self.tema_a, enunciado="e", respuesta="r", puntaje=8))
            s.add(IntentoEjercicio(alumno_id=self.beto, tema_id=self.tema_b, enunciado="e", respuesta="r", puntaje=8))  # otro tema
        por_alumno = {d["alumno_id"]: d for d in tareas.detalle(self.prof, tid)}
        self.assertTrue(por_alumno[self.ana]["hecha"])
        self.assertEqual(por_alumno[self.beto]["avance"], 0)

    def test_nivel_usa_el_nivel_actual(self):
        tid = self.asignar("nivel", 2)
        self.responder(self.ana, 2, dificultad=3)  # 6 XP: Intermedio
        self.responder(self.beto, 1, dificultad=2)  # 2 XP: Principiante
        por_alumno = {d["alumno_id"]: d for d in tareas.detalle(self.prof, tid)}
        self.assertTrue(por_alumno[self.ana]["hecha"])
        self.assertEqual((por_alumno[self.beto]["avance"], por_alumno[self.beto]["hecha"]), (1, False))

    def test_cuantos_cumplieron(self):
        self.asignar("preguntas", 3)
        self.responder(self.ana, 3)
        t = tareas.tareas_de_clase(self.prof, self.clase)[0]
        self.assertEqual((t["alumnos"], t["hechas"], t["vencida"]), (2, 1, False))
        self.assertEqual(t["tema"], "Tema Mat A tareas")
        self.assertEqual(t["descripcion"], "Responder 3 preguntas de examen")

    def test_solo_su_maestro_ve_y_borra(self):
        tid = self.asignar()
        self.assertEqual(tareas.tareas_de_clase(self.otro_prof, self.clase), [])
        self.assertEqual(tareas.detalle(self.otro_prof, tid), [])
        self.assertFalse(tareas.eliminar(self.otro_prof, tid)[0])
        self.assertFalse(tareas.eliminar(self.ana, tid)[0])
        self.assertTrue(tareas.eliminar(self.prof, tid)[0])
        self.assertEqual(tareas.tareas_de_clase(self.prof, self.clase), [])

    # ---- alumno ----
    def test_el_alumno_ve_sus_tareas_ordenadas(self):
        lejana = self.asignar("preguntas", 3, dias=9)
        cercana = self.asignar("preguntas", 3, dias=3)
        hecha = self.asignar("ejercicios", 1, dias=1)
        with get_session() as s:
            s.add(IntentoEjercicio(alumno_id=self.ana, tema_id=self.tema_a, enunciado="e", respuesta="r", puntaje=9))
        lista = tareas.tareas_del_alumno(self.ana)
        self.assertEqual([t["id"] for t in lista], [cercana, lejana, hecha])
        self.assertEqual([t["estado"] for t in lista], ["pendiente", "pendiente", "hecha"])
        self.assertEqual(lista[0]["clase"], "Grupo T")
        self.assertEqual([t["id"] for t in tareas.pendientes(self.ana)], [cercana, lejana])

    def test_quien_no_esta_en_la_clase_no_ve_tareas_ni_los_pendientes_ni_las_inactivas(self):
        self.asignar()
        self.assertEqual(tareas.tareas_del_alumno(self.carla), [])  # no está inscrita
        with get_session() as s:
            s.query(Inscripcion).filter_by(alumno_id=self.beto).update({"estado": "pendiente"})
        self.assertEqual(tareas.tareas_del_alumno(self.beto), [])
        self.assertEqual(len(tareas.tareas_del_alumno(self.ana)), 1)
        self.assertTrue(clases.actualizar(self.prof, self.clase, activa=False)[0])
        self.assertEqual(tareas.tareas_del_alumno(self.ana), [])

    def test_una_tarea_vencida_sin_cumplir(self):
        tid = self.asignar(dias=3)
        with get_session() as s:
            s.get(Tarea, tid).fecha_limite = datetime.now(timezone.utc) - timedelta(days=1)
        self.assertEqual(tareas.tareas_del_alumno(self.ana)[0]["estado"], "vencida")
        self.assertEqual(tareas.pendientes(self.ana), [])
        self.assertTrue(tareas.tareas_de_clase(self.prof, self.clase)[0]["vencida"])

    def test_al_asignar_se_avisa_a_la_clase(self):
        with get_session() as s:
            s.query(Aviso).delete()
        self.asignar("preguntas", 5, dias=4, nota="Repasen sus apuntes.")
        avisos = clases.avisos_para_alumno(self.ana)
        self.assertEqual(len(avisos), 1)
        self.assertIn("Nueva tarea: responder 5 preguntas de examen", avisos[0]["texto"])
        self.assertIn("Tema Mat A tareas", avisos[0]["texto"])
        self.assertIn("Repasen sus apuntes.", avisos[0]["texto"])
        self.assertLessEqual(len(avisos[0]["texto"]), 500)

    def test_matriz_de_cumplimiento(self):
        vacia = tareas.matriz(self.prof, self.clase)
        self.assertEqual(list(vacia.columns), ["Alumno"])
        self.asignar("preguntas", 3)
        self.asignar("preguntas", 3)  # igual a la anterior: las columnas no pueden repetirse
        self.responder(self.ana, 3)
        m = tareas.matriz(self.prof, self.clase)
        self.assertEqual(len(m.columns), 3)
        self.assertEqual(list(m["Alumno"]), ["Ana", "Beto"])
        self.assertEqual(list(m.iloc[:, 1]), ["3/3 ✓", "0/3"])
        self.assertTrue(tareas.matriz(self.otro_prof, self.clase).empty)

    def test_tareas_por_dia_para_el_calendario(self):
        self.asignar("preguntas", 3, dias=3)
        self.asignar("ejercicios", 1, dias=3)
        mapa = tareas.por_dia(self.ana, ZONA)
        dia = (datetime.now(timezone.utc) + timedelta(days=3)).astimezone(ZONA).date()
        self.assertEqual(len(mapa[dia]), 2)
        self.assertIn("Tema Mat A tareas", mapa[dia][0])

    def test_eliminar_la_clase_borra_sus_tareas(self):
        self.asignar()
        self.assertTrue(clases.eliminar_clase(self.prof, self.clase)[0])
        with get_session() as s:
            self.assertEqual(s.query(Tarea).count(), 0)


if __name__ == "__main__":
    unittest.main()
