import unittest

import helpers  # noqa: F401  (configura la base temporal)

from core.voz import texto_para_leer


class TestTextoParaLeer(unittest.TestCase):
    def test_quita_el_formato_y_la_linea_de_fuentes(self):
        md = ("## Conversión de unidades\n\n**Ejemplo resuelto:** convierte *5 km*.\n\n- Paso uno\n- Paso dos\n\n"
              "*Fuentes: Metrología - apuntes.pdf, pág. 3*")
        t = texto_para_leer(md)
        self.assertNotIn("*", t)
        self.assertNotIn("#", t)
        self.assertNotIn("Fuentes", t)
        self.assertNotIn("apuntes.pdf", t)
        self.assertIn("Conversión de unidades.", t)  # el título termina en pausa
        self.assertIn("Paso uno. Paso dos.", t)

    def test_dice_los_simbolos_con_palabras(self):
        t = texto_para_leer("Caudal de 3.0 ft³/min ≈ 1.42 L/s, a 25 °C, con 5 % de error y 2 × 3 = 6.")
        self.assertIn("ft cúbicos", t)
        self.assertIn("aproximadamente 1.42", t)
        self.assertIn("grados Celsius", t)
        self.assertIn("por ciento", t)
        self.assertIn("2 por 3 igual a 6", t)

    def test_formulas_latex(self):
        t = texto_para_leer(r"El resultado es $\frac{84.95}{60} \approx 1.42$ y el área $x^2$, con $$V = I \times R$$")
        self.assertIn("84.95 entre 60", t)
        self.assertIn("aproximadamente 1.42", t)
        self.assertIn("x al cuadrado", t)
        self.assertIn("V igual a I por R", t)
        self.assertNotIn("\\", t)
        self.assertNotIn("$", t)

    def test_potencias_y_unidades_con_diagonal(self):
        t = texto_para_leer(r"Resultado: **1.72 × 10⁷ Pa** y $1.72\times10^{7}\ \text{Pa/psi}$, 3.0 ft³/min a L/s, 10⁻³")
        self.assertIn("1.72 por 10 a la 7 Pa", t)
        self.assertIn("Pa por psi", t)
        self.assertIn("ft cúbicos por min a L por s", t)
        self.assertIn("10 a la menos 3", t)
        self.assertNotIn("\\", t)

    def test_enlaces_codigo_emojis_y_cursor(self):
        t = texto_para_leer("Mira [la tabla](https://x.com) 🎉 y `codigo` ▍")
        self.assertEqual(t, "Mira la tabla y codigo.")

    def test_vacio(self):
        self.assertEqual(texto_para_leer(""), "")
        self.assertEqual(texto_para_leer("*Fuentes: a.pdf*"), "")


class _ComunicadorFalso:
    """Imita a edge_tts.Communicate: devuelve como «audio» los bytes del propio texto."""
    llamadas: list = []

    def __init__(self, texto, voz, rate="+0%"):
        _ComunicadorFalso.llamadas.append((texto, voz, rate))
        self.texto = texto

    async def stream(self):
        yield {"type": "WordBoundary"}
        yield {"type": "audio", "data": self.texto.encode("utf-8")}


class TestVozNatural(unittest.TestCase):
    def setUp(self):
        from core import voz
        voz.audio_natural.cache_clear()
        _ComunicadorFalso.llamadas = []

    def test_trozos_de_frases_completas(self):
        from core.voz import _trozos
        texto = " ".join(f"Frase número {i} del tutor." for i in range(60))
        partes = _trozos(texto, 200)
        self.assertGreater(len(partes), 1)
        self.assertTrue(all(len(p) <= 200 for p in partes))
        self.assertEqual(" ".join(partes), texto)  # no se pierde ni se repite nada
        self.assertTrue(all(p.endswith(".") for p in partes))  # se corta entre frases

    def test_audio_natural_pide_los_trozos_y_los_une_en_orden(self):
        from unittest import mock

        from core import voz
        texto = " ".join(f"Frase {i}." for i in range(200))
        with mock.patch.dict("sys.modules", {"edge_tts": mock.Mock(Communicate=_ComunicadorFalso)}):
            audio = voz.audio_natural(texto, "es-MX-JorgeNeural", "1.2")
        self.assertEqual(audio.decode("utf-8"), "".join(voz._trozos(texto)))  # cada trozo en su lugar, sin perder ninguno
        self.assertGreater(len(_ComunicadorFalso.llamadas), 1)
        self.assertTrue(all(v == "es-MX-JorgeNeural" and r == "+20%" for _, v, r in _ComunicadorFalso.llamadas))

    def test_el_primer_trozo_es_corto_para_que_empiece_pronto(self):
        from core import voz
        texto = " ".join(f"Esta es la frase número {i} de una explicación larga del tutor." for i in range(40))
        partes = voz.trozos_de_voz(texto)
        self.assertLessEqual(len(partes[0]), voz.PRIMER_TROZO)
        self.assertTrue(all(len(p) <= voz.MAX_TROZO for p in partes[1:]))
        self.assertEqual(" ".join(partes), texto)
        self.assertEqual(voz.trozos_de_voz("Una sola frase."), ["Una sola frase."])

    def test_se_entrega_el_trozo_pedido(self):
        from unittest import mock

        from core import voz
        texto = " ".join(f"Frase número {i} de la lección." for i in range(30))
        partes = voz.trozos_de_voz(texto)
        with mock.patch.dict("sys.modules", {"edge_tts": mock.Mock(Communicate=_ComunicadorFalso)}):
            r = voz._audio_para(texto, {"voz": "es-MX-DaliaNeural", "velocidad": "1", "i": 1, "t": "x"})
            fuera = voz._audio_para(texto, {"i": 999, "t": "y"})  # un índice fuera de rango se acota
        import base64
        self.assertEqual((r["i"], r["total"], r["token"]), (1, len(partes), "x"))
        self.assertEqual(base64.b64decode(r["audio"].split(",", 1)[1]).decode("utf-8"), "".join(voz._trozos(partes[1])))
        self.assertEqual(fuera["i"], len(partes) - 1)

    def test_una_voz_desconocida_usa_la_de_por_defecto_y_la_local_se_respalda_en_linea(self):
        from unittest import mock

        from core import voz
        # la voz por defecto es la local; si no se puede generar, se usa la de respaldo en línea
        with mock.patch.dict("sys.modules", {"edge_tts": mock.Mock(Communicate=_ComunicadorFalso)}),                 mock.patch.object(voz, "_audio_local", side_effect=OSError("sin modelo")):
            audio = voz.audio_natural("Hola.", "voz-inventada", "9")
        self.assertEqual(audio, b"Hola.")
        self.assertEqual(_ComunicadorFalso.llamadas, [("Hola.", voz.VOZ_DE_RESPALDO, "+0%")])

    def test_la_voz_local_entrega_un_wav(self):
        from unittest import mock

        import numpy as np

        from core import voz
        kokoro = mock.Mock()
        kokoro.create.return_value = (np.zeros(2400, dtype="float32"), 24000)
        with mock.patch.object(voz, "_kokoro", kokoro):
            wav = voz._audio_local("Hola.", "em_alex", 1.0)
        self.assertEqual(wav[:4], b"RIFF")
        kokoro.create.assert_called_once()
        self.assertEqual(kokoro.create.call_args.kwargs["voice"], "em_alex")
        self.assertEqual(kokoro.create.call_args.kwargs["lang"], "es")

    def test_si_el_servicio_falla_se_avisa_para_usar_la_voz_del_navegador(self):
        from unittest import mock

        from core import voz
        with mock.patch.object(voz, "audio_natural", side_effect=OSError("sin internet")), \
                mock.patch("core.errores.registrar") as registrar:
            r = voz._audio_para("Hola.", {"voz": "es-MX-DaliaNeural", "velocidad": "1", "t": "123"})
        self.assertIsNone(r["audio"])
        self.assertEqual(r["token"], "123")
        self.assertTrue(r["error"])
        registrar.assert_called_once()


if __name__ == "__main__":
    unittest.main()
