import json
import unittest
from unittest import mock

import helpers  # noqa: F401  (configura la base temporal)
import numpy as np
from sqlalchemy import select

from core import examen, llm, material, rag, reticula
from core.db import get_session
from models.schema import Asignacion, Documento, Materia, Tema, Unidad, Usuario
from test_base_datos import BaseDatos

RETICULA = {
    "materia": "Circuitos Eléctricos", "carrera": "Ingeniería Mecatrónica", "cuatrimestre": "Cuatrimestre 2",
    "unidades": [
        {"nombre": "Principios y leyes", "temas": [
            {"nombre": "Leyes básicas", "objetivos": "Saber: Ohm y Kirchhoff."},
            {"nombre": "Circuitos resistivos", "objetivos": "Saber hacer: resistencia equivalente."}]},
        {"nombre": "Análisis en CD", "temas": [{"nombre": "Mallas y nodos", "objetivos": ""}]},
    ],
}


def pregunta_json(texto, correcta):
    return json.dumps({"pregunta": texto, "opciones": ["uno", "dos", "tres", "cuatro"],
                       "indice_correcto": correcta, "resultado": None, "explicacion": "porque sí"})


def revision(respuesta, ambigua=False, motivo="ok"):
    return json.dumps({"respuesta": respuesta, "ambigua": ambigua, "motivo": motivo})


class TestExamen(unittest.TestCase):
    def test_dificultad_inicial_segun_nivel(self):
        self.assertEqual([examen.dificultad_inicial(n) for n in ("apoyo", "normal", "avanzado", "otro")],
                         [1, 2, 3, 2])

    def test_sube_con_aciertos_y_baja_con_fallos_con_limites(self):
        self.assertEqual(examen.siguiente_dificultad(2, True), 3)
        self.assertEqual(examen.siguiente_dificultad(2, False), 1)
        self.assertEqual(examen.siguiente_dificultad(4, True), 4)   # tope
        self.assertEqual(examen.siguiente_dificultad(1, False), 1)  # piso

    def test_flujo_completo_del_examen(self):
        ex = examen.nuevo_examen(3, "normal")
        self.assertEqual((ex["numero"], ex["dificultad"]), (1, 2))
        for acerto in (True, True, False):
            examen.registrar_resultado(ex, acerto)
        self.assertTrue(examen.terminado(ex))
        self.assertEqual([r["dificultad"] for r in ex["resultados"]], [2, 3, 4])  # fue subiendo
        texto = examen.resumen_texto(ex)
        self.assertIn("2/3", texto)
        self.assertIn("avanzada", texto)  # la más alta que resolvió fue la 3

    def test_resumen_sin_aciertos(self):
        ex = examen.nuevo_examen(1, "apoyo")
        examen.registrar_resultado(ex, False)
        self.assertIn("0/1", examen.resumen_texto(ex))


class TestLlmReticula(unittest.TestCase):
    def test_validar_limpia_y_descarta_lo_vacio(self):
        d = llm.validar_reticula({"materia": "  Circuitos \n Eléctricos ", "carrera": "X", "unidades": [
            {"nombre": "U1", "temas": [{"nombre": "T1", "objetivos": "a  b"}, {"nombre": "  "}]},
            {"nombre": "Sin temas", "temas": []}]})
        self.assertEqual(d["materia"], "Circuitos Eléctricos")
        self.assertEqual(len(d["unidades"]), 1)
        self.assertEqual(d["unidades"][0]["temas"], [{"nombre": "T1", "objetivos": "a b"}])

    def test_validar_rechaza_si_no_hay_estructura(self):
        with self.assertRaises(ValueError):
            llm.validar_reticula({"materia": "X", "unidades": []})

    def test_extraer_reticula_usa_la_respuesta_de_la_ia(self):
        with mock.patch.object(llm, "_llamar", return_value=json.dumps(RETICULA)):
            self.assertEqual(llm.extraer_reticula("texto")["unidades"][1]["temas"][0]["nombre"], "Mallas y nodos")

    def test_extraer_reticula_falla_si_la_ia_responde_basura(self):
        with mock.patch.object(llm, "_llamar", return_value="no es json"):
            with self.assertRaises(RuntimeError):
                llm.extraer_reticula("texto")

    def test_quiz_con_opciones_repetidas_se_regenera(self):
        repetido = json.dumps({"pregunta": "p", "opciones": ["54,5 Ω", "60 Ω", "54,5 Ω ", "100 Ω"],
                               "indice_correcto": 0, "explicacion": "e"})
        bueno = json.dumps({"pregunta": "p2", "opciones": ["1", "2", "3", "4"], "indice_correcto": 1,
                            "explicacion": "e"})
        with mock.patch.object(llm, "_llamar", side_effect=[repetido, bueno, revision(1)]) as m:
            d = llm.generar_quiz([{"texto": "x"}], 2)
        self.assertEqual(d["pregunta"], "p2")
        self.assertEqual(m.call_count, 3)  # generar (rechazada), generar, revisar

    def test_quiz_con_clave_que_no_coincide_con_el_calculo_se_regenera(self):
        # la IA calculó 1,92 pero marcó la opción 2,40 como correcta (el defecto real que se encontró)
        mala = json.dumps({"pregunta": "p", "opciones": ["0,96 W", "1,44 W", "2,40 W", "3,84 W"],
                           "indice_correcto": 2, "resultado": 1.92, "explicacion": "P = 1,92 W"})
        buena = json.dumps({"pregunta": "p2", "opciones": ["0,96 W", "1,44 W", "1,92 W", "3,84 W"],
                            "indice_correcto": 2, "resultado": "1,92", "explicacion": "P = V²/R = 1,92 W"})
        with mock.patch.object(llm, "_llamar", side_effect=[mala, buena, revision(2)]) as m:
            d = llm.generar_quiz([{"texto": "x"}], 3)
        self.assertEqual(d["pregunta"], "p2")
        self.assertEqual(m.call_args.kwargs["esfuerzo"], "medium")  # dificultad 3: razona más

    def test_revisor_que_elige_otra_opcion_rechaza_la_pregunta(self):
        with mock.patch.object(llm, "_llamar", side_effect=[
                pregunta_json("mala", 0), revision(3, motivo="el cálculo da otra cosa"),
                pregunta_json("buena", 1), revision(1)]) as m:
            d = llm.generar_quiz([{"texto": "x"}], 2)
        self.assertEqual(d["pregunta"], "buena")
        reintento = m.call_args_list[2].args[0][0]["content"]  # prompt del segundo intento
        self.assertIn("rechazada", reintento)
        self.assertIn("el cálculo da otra cosa", reintento)

    def test_pregunta_que_menciona_el_contexto_se_regenera(self):
        con_contexto = pregunta_json("Según el contexto, ¿cuánto vale R?", 0)
        with mock.patch.object(llm, "_llamar", side_effect=[
                con_contexto, pregunta_json("¿Cuánto vale R?", 0), revision(0)]) as m:
            d = llm.generar_quiz([{"texto": "x"}], 2)
        self.assertEqual(d["pregunta"], "¿Cuánto vale R?")
        self.assertEqual(m.call_count, 3)  # la primera ni siquiera llegó al revisor

    def test_el_revisor_no_ve_la_clave(self):
        with mock.patch.object(llm, "_llamar", return_value=revision(0)) as m:
            llm.verificar_pregunta(json.loads(pregunta_json("p", 0)), [{"texto": "ctx"}])
        enviado = json.dumps(m.call_args.args[0])
        self.assertNotIn("indice_correcto", enviado)
        self.assertNotIn("explicacion", enviado)

    def test_pregunta_ambigua_se_rechaza(self):
        d = json.loads(pregunta_json("p", 0))
        with mock.patch.object(llm, "_llamar", return_value=revision(0, ambigua=True, motivo="no dice si es serie")):
            ok, motivo = llm.verificar_pregunta(d, [{"texto": "x"}])
        self.assertFalse(ok)
        self.assertIn("ambigua", motivo)

    def test_revision_invalida_no_aprueba(self):
        with mock.patch.object(llm, "_llamar", return_value="no es json"):
            ok, _ = llm.verificar_pregunta(json.loads(pregunta_json("p", 0)), [{"texto": "x"}])
        self.assertFalse(ok)

    def test_si_todos_los_intentos_fallan_hay_error_claro(self):
        respuestas = [pregunta_json("p", 0), revision(2)] * llm.MAX_INTENTOS_QUIZ
        with mock.patch.object(llm, "_llamar", side_effect=respuestas):
            with self.assertRaises(RuntimeError):
                llm.generar_quiz([{"texto": "x"}], 2)

    def test_clave_coherente_casos(self):
        ok = {"opciones": ["10 Ω", "20 Ω"], "resultado": 20, "explicacion": "bien"}
        self.assertTrue(llm._clave_coherente(ok, 1))
        self.assertFalse(llm._clave_coherente(ok, 0))
        self.assertTrue(llm._clave_coherente({"opciones": ["a", "b"], "resultado": None, "explicacion": ""}, 0))
        self.assertFalse(llm._clave_coherente({**ok, "explicacion": "la opción más cercana es 20"}, 1))

    def test_el_prompt_exige_preguntas_sin_ambiguedad(self):
        for regla in ("en serie, en paralelo o mixto", "con su unidad", "según el contexto"):
            self.assertIn(regla, llm.SYSTEM_QUIZ)

    def test_dificultades_tienen_instrucciones(self):
        self.assertEqual(set(llm.DIFICULTAD_QUIZ), set(llm.DIFICULTADES))


class TestLecturaDeReticulas(unittest.TestCase):
    def test_cuatrimestre_se_lee_de_la_tabla_de_la_portada(self):
        base = "Tipo de competencia Cuatrimestre Créditos Modalidad Horas por semana Horas Totales {} Escolarizada 7 105"
        self.assertEqual(reticula.cuatrimestre_del_texto(base.format("Base 1 6.56")), "Cuatrimestre 1")
        self.assertEqual(reticula.cuatrimestre_del_texto(base.format("Específica\n2 5.63")), "Cuatrimestre 2")
        self.assertEqual(reticula.cuatrimestre_del_texto("sin tabla"), "")

    def test_las_unidades_no_se_parten_al_dividir(self):
        paginas = ["PORTADA", "Unidad de Aprendizaje I " + "a" * 50, "sigue unidad I " + "b" * 50,
                   "Unidad de Aprendizaje II " + "c" * 50, "Unidad de Aprendizaje III " + "d" * 50]
        partes = reticula.dividir_en_partes(paginas, limite=200)
        self.assertGreater(len(partes), 1)
        self.assertTrue(all(p.startswith("PORTADA") for p in partes))
        con_i = [p for p in partes if "Unidad de Aprendizaje I " in p][0]
        self.assertIn("sigue unidad I", con_i)  # la continuación viaja con su unidad
        for marca in ("Unidad de Aprendizaje II ", "Unidad de Aprendizaje III "):
            self.assertEqual(sum(marca in p for p in partes), 1)  # cada unidad en un solo bloque

    def test_un_documento_corto_va_en_un_solo_bloque(self):
        self.assertEqual(len(reticula.dividir_en_partes(["P", "Unidad de Aprendizaje I x", "Unidad de Aprendizaje II y"])), 1)

    def test_unir_resultados_no_duplica_unidades_ni_temas(self):
        a = {"materia": "M", "carrera": "C", "cuatrimestre": "", "unidades": [
            {"nombre": "Álgebra", "temas": [{"nombre": "T1", "objetivos": ""}]}]}
        b = {"materia": "M", "carrera": "C", "cuatrimestre": "", "unidades": [
            {"nombre": "ALGEBRA", "temas": [{"nombre": "t1", "objetivos": ""}, {"nombre": "T2", "objetivos": ""}]},
            {"nombre": "Trigonometría", "temas": [{"nombre": "T3", "objetivos": ""}]}]}
        r = reticula.unir_resultados([a, b])
        self.assertEqual([u["nombre"] for u in r["unidades"]], ["Álgebra", "Trigonometría"])
        self.assertEqual([t["nombre"] for t in r["unidades"][0]["temas"]], ["T1", "T2"])


class TestClasificacion(unittest.TestCase):
    def test_asigna_el_tema_mas_parecido_y_respeta_el_umbral(self):
        temas = [[1.0, 0.0], [0.0, 1.0]]
        nodos = [[0.9, 0.1], [0.1, 0.9], [0.7, 0.7]]
        self.assertEqual(rag.clasificar_por_similitud(nodos, temas, 0.5), [0, 1, 0])
        self.assertEqual(rag.clasificar_por_similitud(nodos, temas, 0.999), [None, None, None])

    def test_repartir_por_temas_con_embeddings_falsos(self):
        class Nodo:
            def __init__(self, texto):
                self.texto, self.metadata = texto, {}

            def get_content(self, metadata_mode=None):
                return self.texto

        class Modelo:
            def get_text_embedding_batch(self, textos):
                return [[1.0, 0.0] if "ohm" in t.lower() else [0.0, 1.0] for t in textos]

        temas = [{"id": 10, "descripcion": "Ley de Ohm"}, {"id": 20, "descripcion": "Capacitores"}]
        nodos = [Nodo("ohm uno"), Nodo("capacitor"), Nodo("ohm dos")]
        with mock.patch.object(rag, "_embed_model", return_value=Modelo()):
            por_tema, sin = rag.repartir_por_temas(nodos, temas)
        self.assertEqual({k: len(v) for k, v in por_tema.items()}, {10: 2, 20: 1})
        self.assertEqual(sin, 0)


class TestCrearDesdeReticula(BaseDatos):
    def test_crea_la_estructura_y_asigna_al_maestro(self):
        with get_session() as s:
            maestro = Usuario(nombre="Prof", email=f"prof@{self.__class__.__name__}.local",
                              password_hash="x", rol="maestro")
            s.add(maestro)
            s.flush()
            maestro_id = maestro.id
        r = reticula.crear_desde_reticula(RETICULA, "Universidad Retícula", "Ingeniería Mecatrónica",
                                          "Cuatrimestre 2", maestro_id)
        self.assertEqual((r["unidades_nuevas"], r["temas_nuevos"]), (2, 3))
        temas = reticula.temas_de_materia(r["materia_id"])
        self.assertEqual([t["nombre"] for t in temas], ["Leyes básicas", "Circuitos resistivos", "Mallas y nodos"])
        self.assertIn("Ohm y Kirchhoff", temas[0]["descripcion"])
        with get_session() as s:
            self.assertIsNotNone(s.scalar(select(Asignacion.id).where(Asignacion.maestro_id == maestro_id,
                                                                      Asignacion.materia_id == r["materia_id"])))

    def test_editar_la_reticula_cambia_solo_lo_distinto(self):
        r = reticula.crear_desde_reticula(RETICULA, "U Editar", "Carrera", "Cuatrimestre 1")
        mid = r["materia_id"]
        est = reticula.estructura(mid)
        self.assertEqual([u["nombre"] for u in est["unidades"]], ["Principios y leyes", "Análisis en CD"])
        u1, u2 = est["unidades"]
        t_leyes = u1["temas"][0]

        # sin cambios -> nada se modifica
        self.assertEqual(reticula.actualizar(mid, est["nombre"], {u["id"]: u["nombre"] for u in est["unidades"]},
                                             {t["id"]: {"nombre": t["nombre"], "objetivos": t["objetivos"]}
                                              for u in est["unidades"] for t in u["temas"]}), 0)
        n = reticula.actualizar(mid, "  Circuitos Eléctricos I ", {u2["id"]: "Análisis en corriente directa"},
                                {t_leyes["id"]: {"nombre": "Leyes de Ohm y Kirchhoff", "objetivos": "Saber: nuevo"}})
        self.assertEqual(n, 3)
        nuevo = reticula.estructura(mid)
        self.assertEqual(nuevo["nombre"], "Circuitos Eléctricos I")
        self.assertEqual(nuevo["unidades"][1]["nombre"], "Análisis en corriente directa")
        self.assertEqual(nuevo["unidades"][0]["temas"][0]["nombre"], "Leyes de Ohm y Kirchhoff")
        self.assertEqual(nuevo["unidades"][0]["temas"][0]["id"], t_leyes["id"])  # el id (y con él el progreso) se conserva

    def test_editar_rechaza_nombres_vacios_y_ids_ajenos(self):
        a = reticula.crear_desde_reticula(RETICULA, "U Editar 2", "Carrera", "Cuatrimestre 1")["materia_id"]
        otra = {**RETICULA, "materia": "Otra materia"}
        b = reticula.crear_desde_reticula(otra, "U Editar 2", "Carrera", "Cuatrimestre 1")["materia_id"]
        ea, eb = reticula.estructura(a), reticula.estructura(b)
        with self.assertRaises(ValueError):
            reticula.actualizar(a, unidades={ea["unidades"][0]["id"]: "   "})
        with self.assertRaises(ValueError):
            reticula.actualizar(a, temas={ea["unidades"][0]["temas"][0]["id"]: {"nombre": ""}})
        with self.assertRaises(ValueError):  # un tema de la materia B no se puede editar desde la A
            reticula.actualizar(a, temas={eb["unidades"][0]["temas"][0]["id"]: {"nombre": "x"}})
        with self.assertRaises(ValueError):
            reticula.actualizar(a, unidades={eb["unidades"][0]["id"]: "x"})

    def test_repetir_no_duplica_y_ignora_acentos_y_mayusculas(self):
        a = reticula.crear_desde_reticula(RETICULA, "U Repetida", "Carrera", "Cuatrimestre 1")
        cambiada = json.loads(json.dumps(RETICULA))
        cambiada["materia"] = "CIRCUITOS ELECTRICOS"  # sin acento y en mayúsculas
        cambiada["unidades"][0]["temas"][0]["objetivos"] = "Saber: nuevo objetivo."
        b = reticula.crear_desde_reticula(cambiada, "u repetida", "carrera", "cuatrimestre 1")
        self.assertEqual(a["materia_id"], b["materia_id"])
        self.assertEqual((b["unidades_nuevas"], b["temas_nuevos"], b["temas_actualizados"]), (0, 0, 1))
        with get_session() as s:
            self.assertEqual(s.scalar(select(Materia.id).where(Materia.id == a["materia_id"])), a["materia_id"])
            self.assertEqual(len(s.scalars(select(Unidad).where(Unidad.materia_id == a["materia_id"])).all()), 2)


class TestSubirAMateria(BaseDatos):
    def test_reparte_indexa_y_registra_documentos(self):
        r = reticula.crear_desde_reticula(RETICULA, "U Material", "Carrera", "Cuatrimestre 1")
        temas = reticula.temas_de_materia(r["materia_id"])

        class Nodo:
            def __init__(self):
                self.metadata = {}

        n1, n2, n3 = Nodo(), Nodo(), Nodo()
        asignacion = ({temas[0]["id"]: [n1, n2], temas[1]["id"]: [n3]}, 4)
        with mock.patch.object(material.pdf_loader, "extraer_documentos", return_value=[]), \
                mock.patch.object(material.rag, "partir", return_value=[n1, n2, n3]), \
                mock.patch.object(material.rag, "repartir_por_temas", return_value=asignacion), \
                mock.patch.object(material.rag, "indexar_nodos", side_effect=lambda t, nodos: len(nodos)):
            res = material.subir_a_materia(object(), "apuntes.pdf", r["materia_id"], 1)
        self.assertEqual(res["por_tema"], {"Leyes básicas": 2, "Circuitos resistivos": 1})
        self.assertEqual(res["sin_tema"], 4)
        self.assertEqual(n1.metadata["tema_id"], temas[0]["id"])
        with get_session() as s:
            docs = s.scalars(select(Documento).where(Documento.nombre_archivo == "apuntes.pdf")).all()
            self.assertEqual(sorted(d.num_chunks for d in docs), [1, 2])
        self.assertTrue(material.ya_subido(r["materia_id"], "apuntes.pdf"))
        self.assertFalse(material.ya_subido(r["materia_id"], "otro.pdf"))

    def test_cobertura_distingue_material_faltante_e_indice_ausente(self):
        from models.schema import Fragmento
        r = reticula.crear_desde_reticula(RETICULA, "U Cobertura", "Carrera", "Cuatrimestre 1")
        temas = reticula.temas_de_materia(r["materia_id"])
        with get_session() as s:  # tema 0: documento con fragmentos; tema 1: documento SIN fragmentos
            for t, con_fragmento in ((temas[0], True), (temas[1], False)):
                d = Documento(tema_id=t["id"], maestro_id=1, nombre_archivo="apuntes.pdf", num_chunks=1)
                s.add(d)
                s.flush()
                if con_fragmento:
                    s.add(Fragmento(tema_id=t["id"], documento_id=d.id, texto="x", embedding=[0.1, 0.2]))
        cob = {c["tema"]: c for c in material.cobertura(r["materia_id"])}
        self.assertEqual(cob["Leyes básicas"]["estado"], "ok")
        self.assertEqual(cob["Circuitos resistivos"]["estado"], "sin_indice")
        self.assertEqual(cob["Mallas y nodos"]["estado"], "sin_material")
        self.assertEqual(cob["Leyes básicas"]["fragmentos"], 1)

        self.assertEqual(material.eliminar_archivo(r["materia_id"], "apuntes.pdf"), 2)
        despues = {c["tema"]: c["estado"] for c in material.cobertura(r["materia_id"])}
        self.assertEqual(set(despues.values()), {"sin_material"})
        self.assertFalse(material.ya_subido(r["materia_id"], "apuntes.pdf"))

    def test_materia_sin_temas_da_error_claro(self):
        with get_session() as s:
            from models.schema import Carrera, Cuatrimestre, Universidad
            u = Universidad(nombre="U vacía")
            s.add(u)
            s.flush()
            c = Carrera(nombre="C", universidad_id=u.id)
            s.add(c)
            s.flush()
            q = Cuatrimestre(nombre="Q", carrera_id=c.id)
            s.add(q)
            s.flush()
            m = Materia(nombre="Vacía", cuatrimestre_id=q.id)
            s.add(m)
            s.flush()
            mid = m.id
        with self.assertRaises(ValueError):
            material.subir_a_materia(object(), "x.pdf", mid, 1)


if __name__ == "__main__":
    unittest.main()
