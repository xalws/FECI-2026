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


def json_invalido():
    from groq import BadRequestError
    return BadRequestError("Error code: 400 - {'error': {'code': 'json_validate_failed', 'failed_generation': ''}}",
                           response=_respuesta(400), body=None)


class TestJsonInvalido(unittest.TestCase):
    """El modelo a veces devuelve un JSON vacío: se reintenta variando la temperatura y sin culpar a la conexión."""

    def setUp(self):
        p = mock.patch.object(llm.time, "sleep")
        self.dormir = p.start()
        self.addCleanup(p.stop)

    def test_reintenta_con_otra_temperatura_y_sin_esperar(self):
        temperaturas = []
        ok = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"respuesta": 0}'))])
        resultados = [json_invalido(), ok]

        def create(**kw):
            temperaturas.append(kw["temperature"])
            r = resultados.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        falso = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        with mock.patch.object(llm, "_groq", return_value=falso):
            self.assertEqual(llm._llamar([], temperature=0.0, json_mode=True), '{"respuesta": 0}')
        self.assertEqual(len(temperaturas), 2)
        self.assertGreater(temperaturas[1], temperaturas[0])
        self.dormir.assert_not_called()

    def test_si_sigue_fallando_el_mensaje_no_habla_de_la_conexion(self):
        with mock.patch.object(llm, "_groq", return_value=cliente(json_invalido(), json_invalido(), json_invalido())):
            with self.assertRaises(llm.ErrorIA) as e:
                llm._llamar([], json_mode=True)
        self.assertNotIn("conexión", str(e.exception))
        self.assertIn("respuesta válida", str(e.exception))


class TestModeloDeRespaldo(unittest.TestCase):
    """Si el modelo principal llega a su límite de Groq, el tutor sigue con el de respaldo (cada modelo tiene su cuota)."""

    def setUp(self):
        self.dormido = mock.patch.object(llm.time, "sleep")
        self.dormido.start()
        self.addCleanup(self.dormido.stop)
        for nombre, valor in (("GROQ_MODEL", "principal"), ("GROQ_MODEL_RESPALDO", "respaldo"), ("_respaldo_hasta", 0.0)):
            p = mock.patch.object(llm, nombre, valor)
            p.start()
            self.addCleanup(p.stop)

    def cliente_que_anota(self, *resultados):
        modelos, pendientes = [], list(resultados)

        def create(**kw):
            modelos.append(kw["model"])
            r = pendientes.pop(0)
            if isinstance(r, Exception):
                raise r
            return iter(r) if isinstance(r, list) else r

        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))), modelos

    def test_normalmente_usa_el_principal(self):
        c, modelos = self.cliente_que_anota([trozo("ok")])
        with mock.patch.object(llm, "_groq", return_value=c):
            list(llm._llamar_en_vivo([]))
        self.assertEqual(modelos, ["principal"])

    def test_tras_un_limite_pasa_al_respaldo_sin_esperar(self):
        c, modelos = self.cliente_que_anota(limite(), [trozo("listo")])
        with mock.patch.object(llm, "_groq", return_value=c):
            self.assertEqual("".join(llm._llamar_en_vivo([])), "listo")
        self.assertEqual(modelos, ["principal", "respaldo"])
        llm.time.sleep.assert_not_called()  # el respaldo tiene su propia cuota: no hay por qué esperar

    def test_las_llamadas_siguientes_siguen_en_el_respaldo_un_rato(self):
        c, modelos = self.cliente_que_anota(limite(), [trozo("a")], [trozo("b")])
        with mock.patch.object(llm, "_groq", return_value=c):
            list(llm._llamar_en_vivo([]))
            list(llm._llamar_en_vivo([]))
        self.assertEqual(modelos, ["principal", "respaldo", "respaldo"])

    def test_vuelve_al_principal_despues_de_un_minuto(self):
        c, modelos = self.cliente_que_anota(limite(), [trozo("a")], [trozo("b")])
        with mock.patch.object(llm, "_groq", return_value=c):
            list(llm._llamar_en_vivo([]))
            with mock.patch.object(llm.time, "monotonic", return_value=llm._respaldo_hasta + 1):
                list(llm._llamar_en_vivo([]))
        self.assertEqual(modelos, ["principal", "respaldo", "principal"])

    def test_tambien_vale_para_las_respuestas_completas(self):
        ok = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="listo"))])
        c, modelos = self.cliente_que_anota(limite(), ok)
        with mock.patch.object(llm, "_groq", return_value=c):
            self.assertEqual(llm._llamar([]), "listo")
        self.assertEqual(modelos, ["principal", "respaldo"])

    def test_si_el_respaldo_tambien_llega_al_limite_espera_y_avisa(self):
        c, modelos = self.cliente_que_anota(limite(), limite(), limite())
        with mock.patch.object(llm, "_groq", return_value=c):
            with self.assertRaises(llm.ErrorIA) as e:
                list(llm._llamar_en_vivo([]))
        self.assertEqual(e.exception.tipo, "limite")
        self.assertEqual(modelos, ["principal", "respaldo", "respaldo"])

    def test_sin_respaldo_configurado_se_comporta_como_antes(self):
        c, modelos = self.cliente_que_anota(limite(), [trozo("listo")])
        with mock.patch.object(llm, "GROQ_MODEL_RESPALDO", ""), mock.patch.object(llm, "_groq", return_value=c):
            self.assertEqual("".join(llm._llamar_en_vivo([])), "listo")
        self.assertEqual(modelos, ["principal", "principal"])
        llm.time.sleep.assert_called()  # espera y reintenta con el mismo modelo

    def test_el_razonamiento_solo_se_pide_a_modelos_gpt_oss(self):
        with mock.patch.object(llm, "GROQ_MODEL", "llama-x"), mock.patch.object(llm, "GROQ_MODEL_RESPALDO", ""):
            self.assertNotIn("reasoning_effort", llm._kwargs([], 0.1, False, "low"))
        with mock.patch.object(llm, "GROQ_MODEL", "openai/gpt-oss-120b"):
            self.assertEqual(llm._kwargs([], 0.1, False, "low")["reasoning_effort"], "low")


if __name__ == "__main__":
    unittest.main()
