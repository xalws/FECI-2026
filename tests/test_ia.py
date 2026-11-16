"""Respuestas en vivo y errores amables de la IA (sin llamar a Groq: el cliente se simula)."""
import unittest
from types import SimpleNamespace
from unittest import mock

import helpers  # noqa: F401  (configura la base temporal)
import httpx
from groq import AuthenticationError, RateLimitError

from core import llm


def _respuesta(codigo: int) -> httpx.Response:
    return httpx.Response(codigo, request=httpx.Request("POST", "http://groq.test"))


def limite() -> RateLimitError:
    return RateLimitError("límite", response=_respuesta(429), body=None)


def trozo(texto):
    return SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=texto))])


def cliente(*resultados):
    """Cliente falso: cada llamada a create() usa el siguiente resultado (un error o una lista de trozos)."""
    pendientes = list(resultados)

    def create(**_):
        r = pendientes.pop(0)
        if isinstance(r, Exception):
            raise r
        if callable(r):
            return r()
        return iter(r)

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


class TestRespuestaEnVivo(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(llm.time, "sleep")
        p.start()
        self.addCleanup(p.stop)

    def test_entrega_los_trozos_en_orden(self):
        with mock.patch.object(llm, "_groq", return_value=cliente([trozo("Hola"), trozo(None), trozo(" mundo")])):
            self.assertEqual("".join(llm._llamar_en_vivo([{"role": "user", "content": "x"}])), "Hola mundo")

    def test_reintenta_si_el_limite_llega_antes_de_empezar(self):
        with mock.patch.object(llm, "_groq", return_value=cliente(limite(), [trozo("listo")])):
            self.assertEqual("".join(llm._llamar_en_vivo([])), "listo")

    def test_limite_agotado_da_un_mensaje_amable(self):
        with mock.patch.object(llm, "_groq", return_value=cliente(limite(), limite(), limite())):
            with self.assertRaises(llm.ErrorIA) as e:
                list(llm._llamar_en_vivo([]))
        self.assertEqual(e.exception.tipo, "limite")
        self.assertIn("muchas consultas", str(e.exception))
        self.assertTrue(e.exception.detalle)

    def test_error_de_red_agotado(self):
        with mock.patch.object(llm, "_groq", return_value=cliente(*[ConnectionError("sin red")] * 3)):
            with self.assertRaises(llm.ErrorIA) as e:
                list(llm._llamar_en_vivo([]))
        self.assertEqual(e.exception.tipo, "red")
        self.assertIn("conexión", str(e.exception))

    def test_si_se_corta_a_la_mitad_no_se_reintenta(self):
        def corta():
            yield trozo("a medias")
            raise ConnectionError("se cayó")

        with mock.patch.object(llm, "_groq", return_value=cliente(corta)) as g:
            salida = []
            with self.assertRaises(llm.ErrorIA) as e:
                for t in llm._llamar_en_vivo([]):
                    salida.append(t)
        self.assertEqual(salida, ["a medias"])
        self.assertIn("interrumpió", str(e.exception))
        self.assertEqual(g.call_count, 1)

    def test_clave_invalida_no_se_reintenta(self):
        error = AuthenticationError("mala", response=_respuesta(401), body=None)
        with mock.patch.object(llm, "_groq", return_value=cliente(error)):
            with self.assertRaises(llm.ErrorIA) as e:
                list(llm._llamar_en_vivo([]))
        self.assertEqual(e.exception.tipo, "config")

    def test_llamar_normal_tambien_usa_mensajes_amables(self):
        with mock.patch.object(llm, "_groq", return_value=cliente(limite(), limite(), limite())):
            with self.assertRaises(llm.ErrorIA) as e:
                llm._llamar([{"role": "user", "content": "x"}])
        self.assertEqual(e.exception.tipo, "limite")

    def test_sin_material_no_llama_al_modelo(self):
        with mock.patch.object(llm, "_groq", side_effect=AssertionError("no debe llamarse")):
            self.assertEqual(list(llm.responder_en_vivo("Tema", "¿algo?", [], [])), [llm.SIN_INFO])

    def test_responder_sigue_igual(self):
        r = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=r"Fórmula \( V = I R \)"))])
        falso = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: r)))
        with mock.patch.object(llm, "_groq", return_value=falso):
            self.assertEqual(llm.responder("Tema", "p", [{"texto": "t"}], []), "Fórmula $V = I R$")

    def test_el_error_de_ia_es_un_runtime_error(self):
        self.assertTrue(issubclass(llm.ErrorIA, RuntimeError))  # el código anterior sigue capturándolo


if __name__ == "__main__":
    unittest.main()
