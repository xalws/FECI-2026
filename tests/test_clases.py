import unittest
from datetime import datetime, timedelta, timezone

import helpers  # noqa: F401  (configura la base temporal)
from sqlalchemy import select

from core import clases
from core.db import get_session, init_db
from core.passwords import hash_password
from models.schema import (Asignacion, Aviso, Carrera, Clase, Cuatrimestre, Inscripcion, Materia, Unidad, Universidad,
                           Usuario)


def usuario(s, email, rol, activo=True):
    existente = s.scalar(select(Usuario).where(Usuario.email == email))
    if existente:
        return existente.id
    u = Usuario(nombre=email.split("@")[0].title(), email=email, rol=rol, activo=activo,
                password_hash=hash_password("clave123"))
    s.add(u)
    s.flush()
    return u.id


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        with get_session() as s:
            if not s.scalar(select(Universidad.id).where(Universidad.nombre == "U clases")):
                uni = Universidad(nombre="U clases")
                s.add(uni)
                s.flush()
                car = Carrera(nombre="C", universidad_id=uni.id)
                s.add(car)
                s.flush()
                cua = Cuatrimestre(nombre="Cuatrimestre 1", carrera_id=car.id)
                s.add(cua)
                s.flush()
                s.add_all([Materia(nombre="Mat A clases", cuatrimestre_id=cua.id),
                           Materia(nombre="Mat B clases", cuatrimestre_id=cua.id)])
                s.flush()
            cls.mat_a = s.scalar(select(Materia.id).where(Materia.nombre == "Mat A clases"))
            cls.mat_b = s.scalar(select(Materia.id).where(Materia.nombre == "Mat B clases"))
            cls.prof_a = usuario(s, "prof_a@cl.local", "maestro")
            cls.prof_b = usuario(s, "prof_b@cl.local", "maestro")
            cls.prof_baja = usuario(s, "prof_baja@cl.local", "maestro", activo=False)
            cls.admin = usuario(s, "admin@cl.local", "admin")
            cls.ana = usuario(s, "ana@cl.local", "alumno")
            cls.beto = usuario(s, "beto@cl.local", "alumno")
            cls.baja = usuario(s, "baja@cl.local", "alumno", activo=False)
            for prof, mat in ((cls.prof_a, cls.mat_a), (cls.prof_b, cls.mat_b), (cls.prof_baja, cls.mat_a)):
                if not s.scalar(select(Asignacion.id).where(Asignacion.maestro_id == prof, Asignacion.materia_id == mat)):
                    s.add(Asignacion(maestro_id=prof, materia_id=mat))

    def setUp(self):
        with get_session() as s:
            s.query(Aviso).delete()
            s.query(Inscripcion).delete()
            s.query(Clase).delete()

    def clase(self, nombre="Grupo A", prof=None, materia=None, aprobacion=True):
        ok, msg, cid = clases.crear_clase(prof or self.prof_a, materia or self.mat_a, nombre, aprobacion)
        self.assertTrue(ok, msg)
        return cid

    def codigo(self, cid):
        with get_session() as s:
            return s.get(Clase, cid).codigo


class TestCrear(Base):
    def test_el_maestro_crea_clases_de_sus_materias(self):
        cid = self.clase()
        with get_session() as s:
            c = s.get(Clase, cid)
            self.assertEqual((c.nombre, c.maestro_id, c.materia_id, c.activa, c.aprobacion),
                             ("Grupo A", self.prof_a, self.mat_a, True, True))
            self.assertEqual(len(c.codigo), clases.LARGO_CODIGO)
            self.assertTrue(set(c.codigo) <= set(clases.ALFABETO))

    def test_no_puede_crear_de_una_materia_ajena(self):
        ok, msg, cid = clases.crear_clase(self.prof_a, self.mat_b, "Ajena")
        self.assertFalse(ok)
        self.assertIsNone(cid)

    def test_el_administrador_crea_de_cualquiera(self):
        self.assertTrue(clases.crear_clase(self.admin, self.mat_b, "Del admin")[0])

    def test_alumnos_y_cuentas_dadas_de_baja_no_crean(self):
        self.assertFalse(clases.crear_clase(self.ana, self.mat_a, "X")[0])
        self.assertFalse(clases.crear_clase(self.prof_baja, self.mat_a, "X")[0])

    def test_nombres_invalidos_y_repetidos(self):
        self.assertFalse(clases.crear_clase(self.prof_a, self.mat_a, "   ")[0])
        self.assertFalse(clases.crear_clase(self.prof_a, self.mat_a, "x" * 121)[0])
        self.clase("Grupo A")
        self.assertFalse(clases.crear_clase(self.prof_a, self.mat_a, "  grupo   a ")[0])  # mismo nombre sin importar formato
        self.assertTrue(clases.crear_clase(self.prof_a, self.mat_a, "Grupo B")[0])

    def test_los_codigos_no_se_repiten(self):
        codigos = {self.codigo(self.clase(f"G{i}")) for i in range(30)}
        self.assertEqual(len(codigos), 30)

    def test_materias_para_crear(self):
        self.assertEqual(list(clases.materias_para_crear(self.prof_a)), [self.mat_a])
        self.assertIn(self.mat_a, clases.materias_para_crear(self.admin))
        self.assertEqual(clases.materias_para_crear(self.ana), {})


class TestUnirse(Base):
    def test_con_aprobacion_queda_pendiente(self):
        cid = self.clase(aprobacion=True)
        ok, msg = clases.unirse(self.ana, self.codigo(cid))
        self.assertTrue(ok)
        self.assertIn("apruebe", msg)
        self.assertEqual(clases.alumnos_ids(cid), [])
        self.assertEqual(clases.clases_del_alumno(self.ana)[0]["estado"], "pendiente")
        self.assertEqual(clases.materias_del_alumno(self.ana), [])  # pendiente: todavía no cuenta

    def test_sin_aprobacion_entra_al_instante(self):
        cid = self.clase(aprobacion=False)
        self.assertTrue(clases.unirse(self.ana, self.codigo(cid))[0])
        self.assertEqual(clases.alumnos_ids(cid), [self.ana])
        self.assertEqual(clases.materias_del_alumno(self.ana), [self.mat_a])

    def test_el_codigo_se_normaliza(self):
        cid = self.clase(aprobacion=False)
        codigo = self.codigo(cid)
        con_formato = f"  {codigo[:3].lower()}-{codigo[3:].lower()} "
        self.assertTrue(clases.unirse(self.ana, con_formato)[0])

    def test_codigos_invalidos(self):
        self.clase()
        for malo in ("", "ABC", "ZZZZZZ", "A" * 20, None):
            self.assertFalse(clases.unirse(self.ana, malo)[0], malo)

    def test_no_se_une_dos_veces(self):
        cid = self.clase(aprobacion=False)
        codigo = self.codigo(cid)
        self.assertTrue(clases.unirse(self.ana, codigo)[0])
        ok, msg = clases.unirse(self.ana, codigo)
        self.assertFalse(ok)
        self.assertIn("Ya estás", msg)
        with get_session() as s:
            self.assertEqual(len(s.scalars(select(Inscripcion)).all()), 1)

    def test_solicitud_repetida_avisa_que_esta_pendiente(self):
        codigo = self.codigo(self.clase())
        clases.unirse(self.ana, codigo)
        self.assertIn("pendiente", clases.unirse(self.ana, codigo)[1])

    def test_clase_inactiva_no_recibe_alumnos(self):
        cid = self.clase(aprobacion=False)
        clases.actualizar(self.prof_a, cid, activa=False)
        self.assertFalse(clases.unirse(self.ana, self.codigo(cid))[0])

    def test_solo_alumnos_activos_se_unen(self):
        codigo = self.codigo(self.clase(aprobacion=False))
        self.assertFalse(clases.unirse(self.prof_b, codigo)[0])
        self.assertFalse(clases.unirse(self.admin, codigo)[0])
        self.assertFalse(clases.unirse(self.baja, codigo)[0])

    def test_salir(self):
        cid = self.clase(aprobacion=False)
        clases.unirse(self.ana, self.codigo(cid))
        self.assertTrue(clases.salir(self.ana, cid)[0])
        self.assertFalse(clases.salir(self.ana, cid)[0])
        self.assertEqual(clases.alumnos_ids(cid), [])

    def test_clase_desactivada_no_cuenta_para_las_materias_del_alumno(self):
        cid = self.clase(aprobacion=False)
        clases.unirse(self.ana, self.codigo(cid))
        clases.actualizar(self.prof_a, cid, activa=False)
        self.assertEqual(clases.materias_del_alumno(self.ana), [])
        self.assertEqual(len(clases.clases_del_alumno(self.ana)), 1)  # sigue apareciendo en «Mis clases»


class TestGestion(Base):
    def setUp(self):
        super().setUp()
        self.cid = self.clase(aprobacion=True)
        clases.unirse(self.ana, self.codigo(self.cid))
        clases.unirse(self.beto, self.codigo(self.cid))

    def pendientes(self, quien=None):
        return clases.alumnos_de_clase(quien or self.prof_a, self.cid, "pendiente")

    def test_el_maestro_ve_solicitudes_y_aprueba(self):
        self.assertEqual({p["nombre"] for p in self.pendientes()}, {"Ana", "Beto"})
        ana = next(p for p in self.pendientes() if p["nombre"] == "Ana")
        self.assertTrue(clases.resolver_solicitud(self.prof_a, ana["inscripcion_id"], True)[0])
        self.assertEqual(clases.alumnos_ids(self.cid), [self.ana])
        self.assertEqual([p["nombre"] for p in self.pendientes()], ["Beto"])

    def test_rechazar_borra_la_solicitud_y_permite_volver_a_pedir(self):
        beto = next(p for p in self.pendientes() if p["nombre"] == "Beto")
        self.assertTrue(clases.resolver_solicitud(self.prof_a, beto["inscripcion_id"], False)[0])
        self.assertFalse(clases.resolver_solicitud(self.prof_a, beto["inscripcion_id"], False)[0])  # ya no existe
        self.assertTrue(clases.unirse(self.beto, self.codigo(self.cid))[0])

    def test_otro_maestro_no_puede_resolver_ni_ver(self):
        ana = next(p for p in self.pendientes() if p["nombre"] == "Ana")
        self.assertFalse(clases.resolver_solicitud(self.prof_b, ana["inscripcion_id"], True)[0])
        self.assertEqual(clases.alumnos_de_clase(self.prof_b, self.cid, "pendiente"), [])
        self.assertEqual(clases.alumnos_ids(self.cid), [])

    def test_un_alumno_no_puede_resolver_su_propia_solicitud(self):
        ana = next(p for p in self.pendientes() if p["nombre"] == "Ana")
        self.assertFalse(clases.resolver_solicitud(self.ana, ana["inscripcion_id"], True)[0])

    def test_el_administrador_puede_gestionar_cualquier_clase(self):
        ana = next(p for p in self.pendientes(self.admin) if p["nombre"] == "Ana")
        self.assertTrue(clases.resolver_solicitud(self.admin, ana["inscripcion_id"], True)[0])

    def test_quitar_alumno(self):
        for p in self.pendientes():
            clases.resolver_solicitud(self.prof_a, p["inscripcion_id"], True)
        self.assertFalse(clases.quitar_alumno(self.prof_b, self.cid, self.ana)[0])
        self.assertTrue(clases.quitar_alumno(self.prof_a, self.cid, self.ana)[0])
        self.assertFalse(clases.quitar_alumno(self.prof_a, self.cid, self.ana)[0])
        self.assertEqual(clases.alumnos_ids(self.cid), [self.beto])

    def test_cambiar_el_codigo_no_saca_a_nadie_y_el_viejo_deja_de_servir(self):
        for p in self.pendientes():
            clases.resolver_solicitud(self.prof_a, p["inscripcion_id"], True)
        viejo = self.codigo(self.cid)
        ok, nuevo = clases.nuevo_codigo(self.prof_a, self.cid)
        self.assertTrue(ok)
        self.assertNotEqual(viejo, nuevo)
        self.assertEqual(self.codigo(self.cid), nuevo)
        self.assertEqual(len(clases.alumnos_ids(self.cid)), 2)
        self.assertFalse(clases.unirse(self.baja, viejo)[0])
        self.assertFalse(clases.nuevo_codigo(self.prof_b, self.cid)[0])

    def test_actualizar_nombre_y_opciones(self):
        self.assertTrue(clases.actualizar(self.prof_a, self.cid, nombre="  Nuevo   nombre ", aprobacion=False)[0])
        with get_session() as s:
            c = s.get(Clase, self.cid)
            self.assertEqual((c.nombre, c.aprobacion), ("Nuevo nombre", False))
        self.assertFalse(clases.actualizar(self.prof_a, self.cid, nombre="  ")[0])
        self.assertFalse(clases.actualizar(self.prof_b, self.cid, activa=False)[0])

    def test_eliminar_clase_limpia_todo(self):
        clases.publicar_aviso(self.prof_a, self.cid, "Hola")
        self.assertFalse(clases.eliminar_clase(self.prof_b, self.cid)[0])
        self.assertTrue(clases.eliminar_clase(self.prof_a, self.cid)[0])
        with get_session() as s:
            self.assertEqual(s.scalars(select(Clase)).all(), [])
            self.assertEqual(s.scalars(select(Inscripcion)).all(), [])
            self.assertEqual(s.scalars(select(Aviso)).all(), [])

    def test_listado_del_maestro_con_conteos(self):
        ana = next(p for p in self.pendientes() if p["nombre"] == "Ana")
        clases.resolver_solicitud(self.prof_a, ana["inscripcion_id"], True)
        otra = self.clase("De B", prof=self.prof_b, materia=self.mat_b)
        propias = clases.clases_del_maestro(self.prof_a)
        self.assertEqual([c["id"] for c in propias], [self.cid])
        self.assertEqual((propias[0]["alumnos"], propias[0]["pendientes"], propias[0]["materia"]), (1, 1, "Mat A clases"))
        self.assertEqual({c["id"] for c in clases.clases_del_maestro(self.admin)}, {self.cid, otra})
        self.assertEqual(clases.clases_del_maestro(self.ana), [])


class TestAvisos(Base):
    def setUp(self):
        super().setUp()
        self.cid = self.clase(aprobacion=False)
        clases.unirse(self.ana, self.codigo(self.cid))

    def test_publicar_y_ver(self):
        self.assertTrue(clases.publicar_aviso(self.prof_a, self.cid, "  Mañana examen  ")[0])
        avisos = clases.avisos_para_alumno(self.ana)
        self.assertEqual([a["texto"] for a in avisos], ["Mañana examen"])
        self.assertEqual((avisos[0]["clase"], avisos[0]["autor"]), ("Grupo A", "Prof_A"))

    def test_validaciones_y_permisos(self):
        self.assertFalse(clases.publicar_aviso(self.prof_a, self.cid, "   ")[0])
        self.assertFalse(clases.publicar_aviso(self.prof_a, self.cid, "x" * (clases.MAX_AVISO + 1))[0])
        self.assertFalse(clases.publicar_aviso(self.prof_b, self.cid, "intruso")[0])
        self.assertFalse(clases.publicar_aviso(self.ana, self.cid, "el alumno no publica")[0])
        self.assertEqual(clases.avisos_para_alumno(self.ana), [])

    def test_solo_los_alumnos_aceptados_de_clases_activas_los_ven(self):
        clases.publicar_aviso(self.prof_a, self.cid, "Solo para la clase")
        self.assertEqual(clases.avisos_para_alumno(self.beto), [])  # no está en la clase
        cid2 = self.clase("Con aprobación", aprobacion=True)
        clases.unirse(self.beto, self.codigo(cid2))
        clases.publicar_aviso(self.prof_a, cid2, "Para pendientes no")
        self.assertEqual(clases.avisos_para_alumno(self.beto), [])  # pendiente: no ve nada
        clases.actualizar(self.prof_a, self.cid, activa=False)
        self.assertEqual(clases.avisos_para_alumno(self.ana), [])  # clase desactivada

    def test_orden_limite_y_antiguedad(self):
        for i in range(7):
            clases.publicar_aviso(self.prof_a, self.cid, f"aviso {i}")
        with get_session() as s:
            viejo = s.scalar(select(Aviso).where(Aviso.texto == "aviso 0"))
            viejo.fecha = datetime.now(timezone.utc) - timedelta(days=60)
        avisos = clases.avisos_para_alumno(self.ana, limite=5)
        self.assertEqual(len(avisos), 5)
        self.assertNotIn("aviso 0", [a["texto"] for a in avisos])
        self.assertEqual(avisos[0]["texto"], "aviso 6")  # el más nuevo primero

    def test_el_maestro_lista_y_borra_avisos(self):
        clases.publicar_aviso(self.prof_a, self.cid, "uno")
        lista = clases.avisos_de_clase(self.prof_a, self.cid)
        self.assertEqual([a["texto"] for a in lista], ["uno"])
        self.assertEqual(clases.avisos_de_clase(self.prof_b, self.cid), [])
        self.assertFalse(clases.borrar_aviso(self.prof_b, lista[0]["id"])[0])
        self.assertFalse(clases.borrar_aviso(self.ana, lista[0]["id"])[0])
        self.assertTrue(clases.borrar_aviso(self.prof_a, lista[0]["id"])[0])
        self.assertEqual(clases.avisos_de_clase(self.prof_a, self.cid), [])


if __name__ == "__main__":
    unittest.main()
