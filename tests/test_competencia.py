import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import clases, competencia
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import (Asignacion, Carrera, Clase, Conversacion, Cuatrimestre, Inscripcion, IntentoEjercicio, Materia,
                           Quiz, RespuestaQuiz, Tema, Unidad, Universidad, Usuario)

UTC = timezone.utc
HOY = date(2026, 11, 18)  # miércoles; su semana empieza el lunes 16


class TestPuras(unittest.TestCase):
    def test_titulos_por_xp(self):
        self.assertEqual(competencia.nivel_global(0)["nombre"], "Novato")
        self.assertEqual(competencia.nivel_global(24)["nombre"], "Novato")
        self.assertEqual(competencia.nivel_global(25)["nombre"], "Aprendiz")
        self.assertEqual(competencia.nivel_global(299)["nombre"], "Avanzado")
        self.assertEqual(competencia.nivel_global(300)["nombre"], "Experto")
        leyenda = competencia.nivel_global(5000)
        self.assertEqual((leyenda["nombre"], leyenda["siguiente"], leyenda["porcentaje"]), ("Leyenda", None, 100))

    def test_progreso_hacia_el_siguiente_titulo(self):
        n = competencia.nivel_global(50)  # entre 25 y 75
        self.assertEqual((n["nombre"], n["siguiente"], n["porcentaje"]), ("Aprendiz", 75, 50))

    def test_xp_por_semana_en_hora_local(self):
        zona = ZoneInfo("America/Ciudad_Juarez")  # UTC-7
        # lunes 16/nov 03:00 UTC = domingo 15/nov 20:00 local -> cuenta para la semana ANTERIOR
        eventos = [(datetime(2026, 11, 16, 3, 0, tzinfo=UTC), 5), (datetime(2026, 11, 17, 18, 0, tzinfo=UTC), 3),
                   (datetime(2026, 11, 18, 18, 0, tzinfo=UTC), 2), (datetime(2020, 1, 1, tzinfo=UTC), 99)]
        serie = competencia.xp_por_semana(eventos, zona, HOY, semanas=3)
        self.assertEqual([d for d, _ in serie], [date(2026, 11, 2), date(2026, 11, 9), date(2026, 11, 16)])
        self.assertEqual([x for _, x in serie], [0, 5, 5])        # lo muy antiguo no entra

    def test_ranking_con_empates(self):
        filas = [{"nombre": "Zoe", "xp": 10}, {"nombre": "Ana", "xp": 30}, {"nombre": "Beto", "xp": 10},
                 {"nombre": "Carla", "xp": 0}]
        r = competencia.ordenar_ranking(filas)
        self.assertEqual([(f["nombre"], f["posicion"]) for f in r], [("Ana", 1), ("Beto", 2), ("Zoe", 2), ("Carla", 4)])


class TestConBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            uni = Universidad(nombre="U competencia")
            s.add(uni)
            s.flush()
            car = Carrera(nombre="C", universidad_id=uni.id)
            s.add(car)
            s.flush()
            cua = Cuatrimestre(nombre="Cuatrimestre 1", carrera_id=car.id)
            s.add(cua)
            s.flush()
            mat = Materia(nombre="Mat comp", cuatrimestre_id=cua.id)
            s.add(mat)
            s.flush()
            un = Unidad(nombre="U", materia_id=mat.id)
            s.add(un)
            s.flush()
            tema = Tema(nombre="Tema comp", unidad_id=un.id)
            s.add(tema)
            usuarios = {}
            for email, rol in (("ana@co.local", "alumno"), ("beto@co.local", "alumno"), ("carla@co.local", "alumno"),
                               ("ajena@co.local", "alumno"), ("prof@co.local", "maestro"), ("otro@co.local", "maestro"),
                               ("admin@co.local", "admin")):
                u = Usuario(nombre=email.split("@")[0].title(), email=email, rol=rol, password_hash=hash_password("clave123"))
                s.add(u)
                s.flush()
                usuarios[email.split("@")[0]] = u.id
            cls.u = usuarios
            cls.mat, cls.tema = mat.id, tema.id
            clase = Clase(nombre="Grupo", materia_id=mat.id, maestro_id=usuarios["prof"], codigo="COMP01", aprobacion=False)
            s.add(clase)
            s.flush()
            cls.clase = clase.id
            for quien in ("ana", "beto", "carla"):
                s.add(Inscripcion(clase_id=clase.id, alumno_id=usuarios[quien], estado="activo"))
            s.add(Asignacion(maestro_id=usuarios["prof"], materia_id=mat.id))
            conv = Conversacion(alumno_id=usuarios["ana"], tema_id=tema.id, titulo="Examen", tipo="examen")
            s.add(conv)
            s.flush()
            ahora = datetime.now(UTC)
            # ana: 6 respuestas correctas de dificultad 3 (18 XP) hace 20 días + 1 ejercicio de 9 (3 XP) hoy
            for i in range(6):
                q = Quiz(conversacion_id=conv.id, tema_id=tema.id, pregunta=f"p{i}", opciones=["a", "b", "c", "d"],
                         indice_correcto=0, dificultad=3)
                s.add(q)
                s.flush()
                s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=usuarios["ana"], indice_elegido=0, es_correcta=True,
                                    fecha=ahora - timedelta(days=20)))
            s.add(IntentoEjercicio(alumno_id=usuarios["ana"], tema_id=tema.id, enunciado="e", respuesta="r", puntaje=9,
                                   fecha=ahora))
            # beto: 1 correcta de dificultad 2 hoy (2 XP) y una incorrecta (0 XP)
            for i, ok in enumerate((True, False)):
                q = Quiz(conversacion_id=conv.id, tema_id=tema.id, pregunta=f"b{i}", opciones=["a", "b", "c", "d"],
                         indice_correcto=0, dificultad=2)
                s.add(q)
                s.flush()
                s.add(RespuestaQuiz(quiz_id=q.id, alumno_id=usuarios["beto"], indice_elegido=0 if ok else 1, es_correcta=ok,
                                    fecha=ahora))

    def test_xp_de_cada_quien(self):
        total = {f["nombre"]: f["xp"] for f in competencia.ranking(self.clase, UTC)}
        self.assertEqual(total, {"Ana": 21, "Beto": 2, "Carla": 0})

    def test_ranking_total_y_semanal(self):
        r = competencia.ranking(self.clase, UTC)
        self.assertEqual([(f["nombre"], f["posicion"]) for f in r], [("Ana", 1), ("Beto", 2), ("Carla", 3)])
        self.assertEqual(r[0]["titulo"], "Novato")
        semana = {f["nombre"]: f["xp"] for f in competencia.ranking(self.clase, UTC, periodo="semana")}
        # los 18 XP de hace 20 días ya no cuentan esta semana (si hoy es lunes, el ejercicio de hoy sí)
        self.assertEqual(semana, {"Ana": 3, "Beto": 2, "Carla": 0})

    def test_el_ranking_solo_incluye_alumnos_aceptados(self):
        with get_session() as s:
            s.add(Inscripcion(clase_id=self.clase, alumno_id=self.u["ajena"], estado="pendiente"))
        try:
            self.assertEqual({f["nombre"] for f in competencia.ranking(self.clase, UTC)}, {"Ana", "Beto", "Carla"})
        finally:
            with get_session() as s:
                s.query(Inscripcion).filter(Inscripcion.alumno_id == self.u["ajena"]).delete()

    def test_quien_puede_ver_a_quien(self):
        u = self.u
        self.assertTrue(competencia.puede_ver(u["ana"], u["beto"]))         # compañeros de clase
        self.assertTrue(competencia.puede_ver(u["ana"], u["ana"]))          # el suyo
        self.assertFalse(competencia.puede_ver(u["ana"], u["ajena"]))       # sin clase en común
        self.assertFalse(competencia.puede_ver(u["ajena"], u["ana"]))
        self.assertTrue(competencia.puede_ver(u["prof"], u["ana"]))         # su maestro
        self.assertFalse(competencia.puede_ver(u["otro"], u["ana"]))        # otro maestro
        self.assertTrue(competencia.puede_ver(u["admin"], u["ajena"]))      # el administrador ve a todos
        self.assertFalse(competencia.puede_ver(u["ana"], u["prof"]))        # los maestros no tienen perfil público

    def test_un_pendiente_no_ve_ni_es_visto(self):
        with get_session() as s:
            s.add(Inscripcion(clase_id=self.clase, alumno_id=self.u["ajena"], estado="pendiente"))
        try:
            self.assertFalse(competencia.puede_ver(self.u["ajena"], self.u["ana"]))
            self.assertFalse(competencia.puede_ver(self.u["ana"], self.u["ajena"]))
        finally:
            with get_session() as s:
                s.query(Inscripcion).filter(Inscripcion.alumno_id == self.u["ajena"]).delete()

    def test_perfil_publico(self):
        p = competencia.perfil_publico(self.u["beto"], self.u["ana"], UTC)
        self.assertEqual(p["nombre"], "Ana")
        self.assertEqual(p["xp_total"], 21)
        self.assertEqual(p["nivel"]["nombre"], "Novato")
        self.assertEqual(len(p["semanas"]), competencia.SEMANAS_GRAFICA)
        self.assertEqual(sum(x for _, x in p["semanas"]), 21)
        self.assertEqual(len(competencia.solo_semanas(p)), competencia.SEMANAS_GRAFICA)
        self.assertEqual(len(p["logros"]), len(__import__("core.logros", fromlist=["x"]).CATALOGO))
        for clave in ("racha", "minutos_semana", "resumen", "vitrina", "temas_dominados", "xp_semana"):
            self.assertIn(clave, p)

    def test_perfil_negado_sin_permiso(self):
        self.assertIsNone(competencia.perfil_publico(self.u["ajena"], self.u["ana"], UTC))
        self.assertIsNone(competencia.perfil_publico(self.u["ana"], self.u["prof"], UTC))

    def test_temas_dominados(self):
        # 6 correctas de dificultad 3 (18 XP) + ejercicio 9 (3 XP) = 21 XP -> nivel Avanzado (14+)
        dominados = competencia.temas_dominados(self.u["ana"])
        self.assertEqual([(t["tema"], t["materia"], t["nombre_nivel"]) for t in dominados],
                         [("Tema comp", "Mat comp", "Avanzado")])
        self.assertEqual(competencia.temas_dominados(self.u["carla"]), [])
        self.assertEqual(competencia.temas_dominados(self.u["beto"]), [])    # 1 de 2 correctas: nivel bajo


if __name__ == "__main__":
    unittest.main()
