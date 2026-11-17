import unittest
from unittest import mock

import helpers  # noqa: F401  (configura la base temporal)

from core import chat, llm, tutoria
from test_base_datos import BaseDatos


class TestIntencion(unittest.TestCase):
    def test_ordenes_para_iniciar(self):
        for texto in ("comencemos", "Comencemos", "empecemos", "¡Empecemos!", "iniciemos", "vamos a empezar",
                      "iniciar", "podemos comenzar", "empezar"):
            self.assertEqual(tutoria.detectar_intencion(texto), "iniciar", texto)

    def test_ordenes_para_continuar(self):
        for texto in ("continuemos", "continúa", "sigamos", "sigue", "seguimos"):
            self.assertEqual(tutoria.detectar_intencion(texto), "continuar", texto)

    def test_retroalimentacion(self):
        for texto in ("retroalimentación", "dame retroalimentación", "¿qué vimos?", "cómo voy"):
            self.assertEqual(tutoria.detectar_intencion(texto), "retro", texto)

    def test_siguiente_leccion_es_continuar(self):
        for texto in ("siguiente leccion", "Siguiente lección", "siguiente", "la siguiente", "¿Qué sigue?", "y que sigue",
                      "pasemos a la siguiente lección", "avancemos", "adelante"):
            self.assertEqual(tutoria.detectar_intencion(texto), "continuar", texto)

    def test_pasar_al_siguiente_tema_cambia_de_tema(self):
        for texto in ("pasemos al siguiente tema", "Pasemos al siguiente tema", "siguiente tema", "próximo tema", "el siguiente tema",
                      "vamos al siguiente tema", "¿Pasamos al siguiente tema?", "quiero otro tema", "cambiemos de tema",
                      "ya entendí, pasemos al siguiente tema"):
            self.assertEqual(tutoria.detectar_intencion(texto), "siguiente_tema", texto)

    def test_preguntas_sobre_el_siguiente_tema_no_lo_cambian(self):
        for texto in ("¿cuál es el siguiente tema?", "qué tema sigue", "cómo se relaciona con el siguiente tema de la unidad 2"):
            self.assertNotEqual(tutoria.detectar_intencion(texto), "siguiente_tema", texto)

    def test_siguiente_tema_de_la_reticula(self):
        est = {"unidades": [{"id": 1, "nombre": "U1", "temas": [{"id": 10, "nombre": "A"}, {"id": 11, "nombre": "B"}]},
                            {"id": 2, "nombre": "U2", "temas": []},
                            {"id": 3, "nombre": "U3", "temas": [{"id": 30, "nombre": "C"}]}]}
        self.assertEqual(tutoria.siguiente_tema(est, 10), {"tema_id": 11, "nombre": "B", "unidad_id": 1, "unidad": "U1",
                                                         "cambia_unidad": False})
        sig = tutoria.siguiente_tema(est, 11)  # salta la unidad vacía y cambia de unidad
        self.assertEqual((sig["tema_id"], sig["unidad_id"], sig["cambia_unidad"]), (30, 3, True))
        self.assertIsNone(tutoria.siguiente_tema(est, 30))   # el último tema
        self.assertIsNone(tutoria.siguiente_tema(est, 999))  # un tema que no está

    def test_siguiente_dentro_de_una_pregunta_de_contenido_no_se_confunde(self):
        for texto in ("cuál es el siguiente paso para calcular la resistencia equivalente",
                      "¿qué sigue después de aplicar la ley de ohm en un circuito?"):
            self.assertIsNone(tutoria.detectar_intencion(texto), texto)

    def test_consulta_de_busqueda(self):
        hist = [{"rol": "user", "contenido": "qué es la resistividad"}, {"rol": "assistant", "contenido": "La resistividad ρ mide…"}]
        corta = tutoria.consulta_de_busqueda(hist, "como?")
        self.assertIn("como?", corta)
        self.assertIn("La resistividad ρ mide", corta)  # lo último que explicó el tutor
        self.assertIn("qué es la resistividad", corta)
        larga = "explícame cómo se calcula la resistencia equivalente en paralelo"
        self.assertEqual(tutoria.consulta_de_busqueda(hist, larga), larga)
        self.assertEqual(tutoria.consulta_de_busqueda([], "como?"), "como?")

    def test_es_seguimiento(self):
        self.assertTrue(tutoria.es_seguimiento([{"rol": "user", "contenido": "x"}], "como?"))
        self.assertFalse(tutoria.es_seguimiento([], "como?"))
        self.assertFalse(tutoria.es_seguimiento([{"rol": "user", "contenido": "x"}], "explícame la ley de ohm completa por favor"))

    def test_resumen_del_tema(self):
        for texto in ("resumen", "Resumen del tema", "dame un resumen", "hazme el resumen general", "resúmeme el tema"):
            self.assertEqual(tutoria.detectar_intencion(texto), "resumen", texto)
        for texto in ("dame un resumen de la ley de ohm", "resumen de la unidad 2 de circuitos"):
            self.assertIsNone(tutoria.detectar_intencion(texto), texto)  # un resumen de algo concreto es una pregunta

    def test_los_atajos_del_chat_son_preguntas_de_contenido(self):
        for texto in ("Explícamelo más simple", "Dame un ejemplo", "Hazme una pregunta"):
            self.assertIsNone(tutoria.detectar_intencion(texto), texto)

    def test_saludos(self):
        for texto in ("hola", "Hola!", "buenas tardes", "buenos días", "hey"):
            self.assertEqual(tutoria.detectar_intencion(texto), "saludo", texto)

    def test_las_preguntas_de_contenido_no_se_confunden(self):
        for texto in ("¿Qué es la metrología?", "dame un resumen de la ley de ohm",
                      "¿Podemos empezar con el tema de resistencias en serie?",
                      "explícame cómo se calcula la resistencia equivalente en paralelo",
                      "qué es un micrómetro", ""):
            self.assertIsNone(tutoria.detectar_intencion(texto), texto)


class TestPreguntasCongruentes(unittest.TestCase):
    """Las preguntas del tutor deben ser acordes a lo que ya enseñó (ver llm.REGLA_PREGUNTAS)."""

    def test_la_regla_dice_lo_esencial(self):
        r = llm.REGLA_PREGUNTAS
        for idea in ("SOLO sobre lo que ya explicaste", "UN solo punto", "MISMO patrón", "completando un hueco",
                     "traducir oraciones completas", "Nunca escribas la respuesta", "UN solo paso", "MISMO punto",
                     "baja la dificultad"):
            self.assertIn(idea, r)

    def test_la_leccion_el_continuar_y_el_chat_la_incluyen(self):
        for prompt in (tutoria.SYSTEM_INICIAR, tutoria.SYSTEM_CONTINUAR, llm.SYSTEM_TUTOR):
            self.assertIn(llm.REGLA_PREGUNTAS, prompt)

    def test_la_leccion_explica_un_solo_punto_y_el_continuar_no_repasa_todo(self):
        self.assertIn("SOLO el primer punto", tutoria.SYSTEM_INICIAR)
        self.assertIn("UN solo punto nuevo", tutoria.SYSTEM_CONTINUAR)
        self.assertIn("sin títulos grandes", tutoria.SYSTEM_INICIAR)

    def test_los_prompts_se_pueden_formatear(self):  # las llaves del texto romperían .format
        self.assertIn("Inglés", llm.SYSTEM_TUTOR.format(tema="Inglés", sin_info="x"))
        self.assertIn("Inglés", tutoria._sistema(tutoria.SYSTEM_INICIAR, "Inglés", "normal"))
        self.assertIn("Inglés", tutoria._sistema(tutoria.SYSTEM_CONTINUAR, "Inglés", "normal"))

    def test_los_niveles_piden_preguntas_acordes(self):
        self.assertIn("reconocer o completar", llm.AJUSTE_TUTOR["apoyo"])
        self.assertIn("ejemplos del contexto", llm.AJUSTE_TUTOR["avanzado"])


class TestRespuestaAUnaPreguntaDelTutor(unittest.TestCase):
    TUTOR = {"rol": "assistant", "contenido": "Explicación del tema…\n\n**Pregunta de comprobación**\n"
                                              "¿Cuál es la preposición que usamos para decir la hora en inglés?"}

    def test_una_respuesta_corta_a_la_pregunta_del_tutor(self):
        self.assertEqual(llm.pregunta_abierta([self.TUTOR], "at"),
                         "¿Cuál es la preposición que usamos para decir la hora en inglés?")
        self.assertIsNotNone(llm.pregunta_abierta([self.TUTOR], "Se usa at para las horas exactas"))

    def test_si_el_alumno_pregunta_o_escribe_mucho_es_otra_cosa(self):
        self.assertIsNone(llm.pregunta_abierta([self.TUTOR], "¿y con los días?"))
        self.assertIsNone(llm.pregunta_abierta([self.TUTOR], "explícame con más detalle cómo funcionan las preposiciones de "
                                                             "tiempo en inglés cuando hablamos de horas, días y fechas largas, "
                                                             "y también cuándo se usan en otros contextos distintos"))
        self.assertIsNone(llm.pregunta_abierta([self.TUTOR], "   "))

    def test_sin_pregunta_abierta(self):
        self.assertIsNone(llm.pregunta_abierta([], "at"))
        self.assertIsNone(llm.pregunta_abierta([{"rol": "assistant", "contenido": "Eso es todo por hoy."}], "at"))
        self.assertIsNone(llm.pregunta_abierta([{"rol": "user", "contenido": "¿qué es at?"}], "at"))  # el último fue del alumno

    def test_toma_la_ultima_pregunta_del_mensaje_del_tutor(self):
        tutor = {"rol": "assistant", "contenido": "¿Entendiste?\nExplico otra vez.\n- ¿Qué preposición va con las horas?"}
        self.assertEqual(llm.pregunta_abierta([tutor], "at"), "¿Qué preposición va con las horas?")

    def test_el_mensaje_al_modelo_pide_evaluar_la_respuesta(self):
        frag = [{"texto": "Usa at para horas exactas.", "score": 1.0}]
        con = llm._mensajes_tutor("Inglés", "at", frag, [self.TUTOR], "normal")[-1]["content"]
        self.assertIn("contestando tu última pregunta", con)
        self.assertIn("RESPUESTA DEL ALUMNO: at", con)
        self.assertIn("evalúa su respuesta", con)
        sin = llm._mensajes_tutor("Inglés", "¿qué es at?", frag, [self.TUTOR], "normal")[-1]["content"]
        self.assertIn("MENSAJE DEL ALUMNO: ¿qué es at?", sin)
        self.assertNotIn("contestando", sin)

    def test_la_regla_del_tutor_lo_menciona(self):
        self.assertIn("EVALÚALA", llm.SYSTEM_TUTOR)

    def test_los_atajos_y_las_peticiones_no_se_califican(self):
        for pedido in ("Hazme una pregunta", "Dame un ejemplo", "Explícamelo más simple", "Resumen del tema",
                       "explícame otra vez", "otra pregunta", "no entiendo", "Plantéame un ejercicio práctico sobre este tema."):
            self.assertTrue(llm.es_peticion(pedido), pedido)
            self.assertIsNone(llm.pregunta_abierta([self.TUTOR], pedido), pedido)
        for respuesta in ("at", "no sé", "8 V", "la estética", "Dignidad"):  # «no sé» sí es una respuesta: se corrige
            self.assertFalse(llm.es_peticion(respuesta), respuesta)

    def test_detecta_preguntas_de_completar_y_las_que_siguen_al_encabezado(self):
        completar = {"rol": "assistant", "contenido": "Ejemplo: *I get up at 7:00.*\n\n**Pregunta de comprobación**\n"
                                                     "*I start work ___ 9:00 a.m.* (elige la preposición correcta)."}
        self.assertIn("___", llm.pregunta_abierta([completar], "at"))
        encabezado = {"rol": "assistant", "contenido": "**Pregunta de comprobación**\nResuelve: $5z-2=13$.\n*(Pista: suma 2.)*"}
        self.assertEqual(llm.pregunta_abierta([encabezado], "z = 3"), "Resuelve: $5z-2=13$.")


class TestMaterialFaltante(unittest.TestCase):
    def test_solo_las_preguntas_de_contenido_cuentan_como_material_faltante(self):
        for texto in ("¿Qué es la trazabilidad?", "como convierto psi a pascales", "¿Quién inventó el micrómetro?"):
            self.assertTrue(chat.señala_material_faltante(texto), texto)
        for texto in ("como?", "ok", "y eso?", "Dame un ejemplo", "Hazme una pregunta", "Explícamelo más simple"):
            self.assertFalse(chat.señala_material_faltante(texto), texto)


class TestVocabularioDelAlumno(unittest.TestCase):
    """El alumno no sabe qué es «el contexto» (así llama el modelo al material): se le dice «el material»."""

    def test_las_citas_al_contexto_se_vuelven_material(self):
        casos = {"tal como indica el ejemplo resuelto en el contexto.": "tal como indica el ejemplo resuelto en el material.",
                 "Según el contexto, la preposición es at.": "Según el material, la preposición es at.",
                 "como se indica en el contexto dado.": "como se indica en el material.",
                 "Es correcto (ver el contexto).": "Es correcto (ver el material)."}
        for antes, despues in casos.items():
            self.assertEqual(llm._formato_latex(antes), despues)

    def test_no_toca_usos_del_tema(self):
        for texto in ("El contexto comunicativo influye en el mensaje.", "Analiza el contexto histórico de la norma.",
                      "En el contexto de una fábrica, se mide la presión"):
            self.assertEqual(llm._formato_latex(texto), texto)


class TestNoRevelarLaRespuesta(unittest.TestCase):
    def test_quita_la_respuesta_de_la_pregunta_final(self):
        texto = ("**Ejemplo**: Estudiante tiene Legajo.\n\n**Pregunta de comprobación**\n"
                 "¿Qué atributo de *Profesor* sería la clave primaria?\n(Respuesta: LegajoProf)")
        limpio = llm.quitar_respuesta_revelada(texto)
        self.assertNotIn("LegajoProf", limpio)
        self.assertIn("¿Qué atributo de *Profesor* sería la clave primaria?", limpio)

    def test_quita_variantes(self):
        for cola in ("(Respuesta esperada: tabla Préstamo con ID_Socio)", "(**Respuesta**: escrita)",
                     "Respuesta esperada: 6.75 V", "**Respuesta correcta:** at"):
            texto = f"Explicación.\n\n**Pregunta**\n¿Cuál es el valor?\n{cola}"
            self.assertNotIn(cola.split(":")[-1].strip(" *)"), llm.quitar_respuesta_revelada(texto), cola)

    def test_respeta_los_ejemplos_resueltos_de_antes_de_la_pregunta(self):
        texto = ("**Ejemplo resuelto**\nV = 2 A × 4 Ω. Respuesta: 8 V.\n\n**Pregunta de comprobación**\n"
                 "Con I = 3 A y R = 2 Ω, ¿cuál es el voltaje?\n*(Pista: usa V = I × R.)*")
        self.assertEqual(llm.quitar_respuesta_revelada(texto), texto)  # el ejemplo conserva su resultado y la pista sigue

    def test_los_titulos_grandes_se_vuelven_negritas(self):
        texto = "### 1. Expresiones de hora\nUsa **at**.\n\n# Pregunta\n¿Qué va en *I wake up ___ 7*?"
        limpio = llm.quitar_respuesta_revelada(texto)
        self.assertNotIn("#", limpio)
        self.assertIn("**1. Expresiones de hora**", limpio)
        self.assertIn("**Pregunta**", limpio)

    def test_la_regla_pide_que_la_pregunta_no_traiga_su_respuesta(self):
        self.assertIn("deja el hueco ___", llm.REGLA_PREGUNTAS)
        self.assertIn("no copies tal cual un ejemplo ya resuelto", llm.REGLA_PREGUNTAS)

    def test_sin_pregunta_no_cambia_nada(self):
        texto = "Resumen: la respuesta: es así.\n(Respuesta: nada)"
        self.assertEqual(llm.quitar_respuesta_revelada("Solo una explicación."), "Solo una explicación.")
        self.assertTrue(llm.quitar_respuesta_revelada(texto))

    def test_la_regla_de_preguntas_pide_no_preguntar_lo_no_visto_ni_pistas_que_revelen(self):
        self.assertIn("La respuesta debe poder sacarse de lo que ya mostraste", llm.REGLA_PREGUNTAS)
        self.assertIn("no dice la respuesta ni la deja obvia", llm.REGLA_PREGUNTAS)


class TestRespuestasDelTutor(unittest.TestCase):
    FRAG = [{"texto": "La metrología es la ciencia de la medición.", "score": 1.0, "archivo": "", "pagina": ""}]

    def test_iniciar_usa_objetivos_y_material(self):
        with mock.patch.object(llm, "_llamar", return_value="Intro de la lección") as m:
            r = tutoria.iniciar_leccion("Metrología", "Saber: definir metrología.", self.FRAG, "apoyo")
        self.assertEqual(r, "Intro de la lección")
        enviado = m.call_args.args[0]
        self.assertIn("Saber: definir metrología.", enviado[1]["content"])
        self.assertIn("ciencia de la medición", enviado[1]["content"])
        self.assertIn("le está costando", enviado[0]["content"])  # el nivel de refuerzo también aplica aquí

    def test_iniciar_sin_material_no_llama_a_la_ia_y_muestra_la_reticula(self):
        with mock.patch.object(llm, "_llamar") as m:
            r = tutoria.iniciar_leccion("Metrología", "Saber: definir metrología.", [], "normal")
        m.assert_not_called()
        self.assertIn("Por ahora no puedo dar la lección", r)
        self.assertIn("definir metrología", r)

    def test_sin_material_distingue_nunca_subido_de_subido_pero_no_disponible(self):
        with mock.patch.object(llm, "_llamar") as m:
            nunca = tutoria.iniciar_leccion("Aislantes", "Saber: x", [], "normal", "sin_material")
            no_disp = tutoria.iniciar_leccion("Aislantes", "Saber: x", [], "normal", "sin_indice")
        m.assert_not_called()
        self.assertIn("todavía no ha subido", nunca)
        self.assertNotIn("ya fue cargado", nunca)
        self.assertIn("ya fue cargado", no_disp)  # el material existe pero no está disponible
        self.assertIn("lo vuelva a cargar", no_disp)
        self.assertNotIn("todavía no ha subido", no_disp)  # ya no se culpa al maestro de algo que sí hizo

    def test_continuar_incluye_la_conversacion(self):
        historial = [{"rol": "user", "contenido": "¿Qué es medir?"}, {"rol": "assistant", "contenido": "Medir es comparar."}]
        with mock.patch.object(llm, "_llamar", return_value="Sigamos con…") as m:
            tutoria.continuar_leccion("Metrología", historial, self.FRAG)
        contenido = m.call_args.args[0][1]["content"]
        self.assertIn("Alumno: ¿Qué es medir?", contenido)
        self.assertIn("Tutor: Medir es comparar.", contenido)

    def test_retroalimentar_y_continuar_sin_historial_no_llaman_a_la_ia(self):
        with mock.patch.object(llm, "_llamar") as m:
            self.assertEqual(tutoria.retroalimentar("T", [], self.FRAG), tutoria.SIN_HISTORIAL)
            self.assertEqual(tutoria.continuar_leccion("T", [], self.FRAG), tutoria.SIN_HISTORIAL)
        m.assert_not_called()

    def test_resumir_pide_la_estructura_y_sin_material_no_llama_a_la_ia(self):
        with mock.patch.object(llm, "_llamar", return_value="Resumen") as m:
            self.assertEqual(tutoria.resumir_tema("Metrología", "Saber: x", self.FRAG), "Resumen")
        for parte in ("Idea central", "Conceptos clave", "Qué suelen confundir"):
            self.assertIn(parte, m.call_args.args[0][0]["content"])
        with mock.patch.object(llm, "_llamar") as m:
            self.assertIn("no hay material", tutoria.resumir_tema("Metrología", "", []))
        m.assert_not_called()

    def test_retroalimentar_pide_las_tres_partes(self):
        with mock.patch.object(llm, "_llamar", return_value="ok") as m:
            tutoria.retroalimentar("T", [{"rol": "user", "contenido": "hola"}], [])
        for parte in ("Lo que ya vimos", "dudas o fallos", "repasar o practicar"):
            self.assertIn(parte, m.call_args.args[0][0]["content"])


class TestConversacionesDelTema(BaseDatos):
    def test_solo_chats_con_mensajes_del_tema(self):
        chat_ok = chat.crear_conversacion(self.alumno_id, self.tema_id, "Mi duda sobre Ohm")
        chat.guardar_mensaje(chat_ok, "user", "hola")
        vacia = chat.crear_conversacion(self.alumno_id, self.tema_id, "Vacía")
        examen_id = chat.crear_conversacion(self.alumno_id, self.tema_id, "Examen", "examen")
        ejercicio_id = chat.crear_conversacion(self.alumno_id, self.tema_id, "Ejercicio práctico", "ejercicio")
        for c in (examen_id, ejercicio_id):
            chat.guardar_mensaje(c, "assistant", "x")
        antigua = chat.crear_conversacion(self.alumno_id, self.tema_id, "Examen")  # sin tipo útil: título antiguo
        chat.guardar_mensaje(antigua, "assistant", "x")

        ids = [c["id"] for c in chat.conversaciones_del_tema(self.alumno_id, self.tema_id)]
        self.assertIn(chat_ok, ids)
        for excluida in (vacia, examen_id, ejercicio_id, antigua):
            self.assertNotIn(excluida, ids)
        self.assertEqual(chat.conversaciones_del_tema(self.alumno_id, self.tema_id + 999), [])

    def test_las_mas_recientes_van_primero(self):
        a = chat.crear_conversacion(self.alumno_id, self.tema_id, "primera")
        b = chat.crear_conversacion(self.alumno_id, self.tema_id, "segunda")
        for c in (a, b):
            chat.guardar_mensaje(c, "user", "x")
        ids = [c["id"] for c in chat.conversaciones_del_tema(self.alumno_id, self.tema_id)]
        self.assertLess(ids.index(b), ids.index(a))


if __name__ == "__main__":
    unittest.main()
