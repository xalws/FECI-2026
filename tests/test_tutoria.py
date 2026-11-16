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

    def test_saludos(self):
        for texto in ("hola", "Hola!", "buenas tardes", "buenos días", "hey"):
            self.assertEqual(tutoria.detectar_intencion(texto), "saludo", texto)

    def test_las_preguntas_de_contenido_no_se_confunden(self):
        for texto in ("¿Qué es la metrología?", "dame un resumen de la ley de ohm",
                      "¿Podemos empezar con el tema de resistencias en serie?",
                      "explícame cómo se calcula la resistencia equivalente en paralelo",
                      "qué es un micrómetro", ""):
            self.assertIsNone(tutoria.detectar_intencion(texto), texto)


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
