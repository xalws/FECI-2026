"""El tutor habla: lectura en voz alta de sus respuestas.

Por defecto se usa una voz natural (neuronal) de Microsoft en español de México, generada en el servidor con el paquete
edge-tts: suena casi humana y se oye igual en cualquier navegador o celular. No usa la cuota del modelo de lenguaje.
Si ese servicio no responde (sin internet, por ejemplo), habla la voz que traiga el navegador (Web Speech API).

- `texto_para_leer` quita del mensaje lo que no se debe leer (formato, la línea de fuentes) y dice los símbolos con
  palabras ("ft³" → "ft cúbicos", "≈" → "aproximadamente").
- `lector` dibuja bajo cada respuesta los botones «Escuchar / Pausar» y «Detener». Si el alumno activó la lectura
  automática, lee solo las respuestas nuevas.
- `ajustes` es el panel de «Mi cuenta» para elegir voz, velocidad y lectura automática. Se guardan en el navegador
  (cada dispositivo tiene sus propias voces), no en la base de datos.
"""
import asyncio
import base64
import functools
import re
import unicodedata

import streamlit as st

# ---------------------------------------------------------------------------------------------------------------
# Texto que se lee
# ---------------------------------------------------------------------------------------------------------------
_SIMBOLOS = [
    ("≈", " aproximadamente "), ("≠", " diferente de "), ("≤", " menor o igual que "), ("≥", " mayor o igual que "),
    ("×", " por "), ("÷", " entre "), ("·", " por "), ("±", " más menos "), ("→", ", "), ("⇒", ", entonces "), ("⟹", ", entonces "), ("⇔", ", equivale a "),
    ("√", " raíz de "), ("π", " pi "), ("Ω", " ohms "), ("µ", " micro"), ("μ", " micro"), ("Δ", " delta "),
    ("°C", " grados Celsius"), ("°F", " grados Fahrenheit"), ("°", " grados"), ("%", " por ciento"),
    ("²", " cuadrados"), ("³", " cúbicos"), ("¹", ""), ("=", " igual a "), ("<", " menor que "), (">", " mayor que "),
]
_SUPER = str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "-0123456789")
_LATEX = [
    (r"\\times", " por "), (r"\\cdot", " por "), (r"\\div", " entre "), (r"\\approx", " aproximadamente "),
    (r"\\pm", " más menos "), (r"\\leq?", " menor o igual que "), (r"\\geq?", " mayor o igual que "),
    (r"\\neq", " diferente de "), (r"\\pi", " pi "), (r"\\Omega", " ohms "), (r"\\Delta", " delta "),
    (r"\\mu", " micro"), (r"\\%", " por ciento"), (r"\\,|\\;|\\!|\\quad|\\qquad|\\ ", " "),
]


def _formula_en_palabras(formula: str) -> str:
    f = formula
    f = re.sub(r"\\text\{([^{}]*)\}|\\mathrm\{([^{}]*)\}", lambda m: m.group(1) or m.group(2) or "", f)
    for _ in range(3):  # fracciones anidadas
        f = re.sub(r"\\[dt]?frac\{([^{}]*)\}\{([^{}]*)\}", r" \1 entre \2 ", f)
    f = re.sub(r"\\sqrt\{([^{}]*)\}", r" raíz de \1 ", f)
    f = re.sub(r"\^\{?2\}?", " al cuadrado", f)
    f = re.sub(r"\^\{?3\}?", " al cubo", f)
    f = re.sub(r"\^\{([^{}]*)\}|\^(\S)", lambda m: f" a la {m.group(1) or m.group(2)}", f)
    f = re.sub(r"_\{([^{}]*)\}|_(\w)", lambda m: f" {m.group(1) or m.group(2)}", f)
    for patron, palabra in _LATEX:
        f = re.sub(patron, palabra, f)
    f = re.sub(r"\\[a-zA-Z]+", " ", f)  # cualquier otro comando
    return f.replace("{", " ").replace("}", " ")


def texto_para_leer(markdown: str) -> str:
    """El mensaje del tutor convertido en texto para decirlo en voz alta."""
    t = markdown or ""
    t = re.sub(r"(?im)^\s*[*_]*\s*fuentes\s*:.*$", "", t)            # la línea de fuentes no se lee
    t = t.replace("▍", "")
    t = re.sub(r"\$\$(.+?)\$\$", lambda m: ". " + _formula_en_palabras(m.group(1)) + ". ", t, flags=re.S)
    t = re.sub(r"\$([^$\n]+)\$", lambda m: _formula_en_palabras(m.group(1)), t)
    t = re.sub(r"```.*?```", " ", t, flags=re.S)                      # bloques de código
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)                       # imágenes
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)                   # enlaces: solo el texto
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*(.+)$", r"\1.", t)             # títulos: con pausa al final
    t = re.sub(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s+", "", t)              # viñetas y listas numeradas
    t = re.sub(r"(?m)^\s*>\s?", "", t)                               # citas
    t = re.sub(r"(?m)^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", " ", t)        # separadores
    t = re.sub(r"\|", ", ", t)                                       # celdas de tabla
    t = re.sub(r"[*_`~]+", "", t)                                    # negritas, cursivas, código
    # Potencias con superíndices: «10⁷» → «10 a la 7» (tras una letra, como «ft³», se leen como unidad: «ft cúbicos»)
    t = re.sub(r"(\d)([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+)", lambda m: f"{m.group(1)} a la {m.group(2).translate(_SUPER).replace('-', 'menos ')}", t)
    t = re.sub(r"(?<=[A-Za-zµμ²³])/(?=[A-Za-z])", " por ", t)  # unidades: «L/s» → «L por s»
    for simbolo, palabra in _SIMBOLOS:
        t = t.replace(simbolo, palabra)
    t = "".join(c for c in t if unicodedata.category(c) not in ("So", "Cs", "Co"))  # emojis y similares
    t = re.sub(r"(?m)([^.:;!?,\s])\s*$", r"\1.", t)                  # cada línea termina en pausa
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s+([.,;:!?])", r"\1", t)
    t = re.sub(r"([.,;:])(?:\s*[.,;:])+", r"\1", t)                  # «. .» o «:.» repetidos
    return t.strip(" ,;")


# ---------------------------------------------------------------------------------------------------------------
# Voz natural generada en el servidor (voces neuronales de Microsoft, con el paquete edge-tts)
# ---------------------------------------------------------------------------------------------------------------
VOCES_NATURALES = {"es-MX-DaliaNeural": "Dalia · voz natural de mujer (México)",
                   "es-MX-JorgeNeural": "Jorge · voz natural de hombre (México)"}
VOZ_NATURAL_DEFECTO = "es-MX-JorgeNeural"
VELOCIDADES = {"0.8": "-20%", "1": "+0%", "1.2": "+20%"}  # la del navegador → la de edge-tts
PRIMER_TROZO = 140    # caracteres del primer trozo: corto, para que la voz empiece a sonar en un par de segundos
MAX_TROZO = 400       # los demás trozos se generan mientras suena el anterior
LIMITE_SEGUNDOS = 25  # si el servicio no responde, se usa la voz del navegador
_AUDIOS_GUARDADOS = 12  # respuestas por sesión que se conservan en el servidor


def _trozos(texto: str, maximo: int = MAX_TROZO) -> list[str]:
    """Parte el texto en trozos de frases completas, ninguno (salvo una frase muy larga) mayor que `maximo`."""
    salida: list[str] = []
    for frase in re.findall(r"[^.!?;:]+[.!?;:]*", texto) or [texto]:
        frase = frase.strip()
        if not frase:
            continue
        if salida and len(salida[-1]) + 1 + len(frase) <= maximo:
            salida[-1] += " " + frase
        else:
            salida.append(frase)
    return salida


def trozos_de_voz(texto: str) -> list[str]:
    """Trozos en que se genera el audio: el primero corto (empieza a sonar pronto) y los demás más largos."""
    primeros = _trozos(texto, PRIMER_TROZO)
    if len(primeros) <= 1:
        return primeros
    return [primeros[0], *_trozos(" ".join(primeros[1:]), MAX_TROZO)]


@functools.lru_cache(maxsize=256)
def audio_natural(texto: str, voz: str = VOZ_NATURAL_DEFECTO, velocidad: str = "1") -> bytes:
    """MP3 de un trozo de texto con una voz natural (se guarda: volver a escucharlo no lo genera otra vez)."""
    import edge_tts  # se importa aquí: solo hace falta cuando alguien pide escuchar

    voz = voz if voz in VOCES_NATURALES else VOZ_NATURAL_DEFECTO
    rate = VELOCIDADES.get(str(velocidad), "+0%")

    async def uno(trozo: str) -> bytes:
        audio = bytearray()
        async for parte in edge_tts.Communicate(trozo, voz, rate=rate).stream():
            if parte["type"] == "audio":
                audio += parte["data"]
        return bytes(audio)

    async def todos() -> list[bytes]:  # un texto muy largo se pide en partes a la vez (los MP3 se pueden unir)
        return await asyncio.wait_for(asyncio.gather(*(uno(t) for t in _trozos(texto))), LIMITE_SEGUNDOS)

    partes = asyncio.run(todos())
    if not partes or not all(partes):
        raise RuntimeError("El servicio de voz no devolvió audio.")
    return b"".join(partes)


def _audio_para(texto: str, pedido: dict) -> dict:
    """El audio del trozo pedido (en base64) para el componente, o un error (entonces habla la voz del navegador)."""
    voz, velocidad = pedido.get("voz") or VOZ_NATURAL_DEFECTO, str(pedido.get("velocidad") or "1")
    partes = trozos_de_voz(texto)
    i = min(max(int(pedido.get("i") or 0), 0), max(len(partes) - 1, 0))
    respuesta = {"token": pedido.get("t"), "i": i, "total": len(partes)}
    try:
        mp3 = audio_natural(partes[i], voz, velocidad)
        return {**respuesta, "audio": base64.b64encode(mp3).decode("ascii"), "error": None}
    except Exception as e:  # sin internet, servicio caído…: el alumno escucha igual, con la voz del navegador
        from core import errores
        errores.registrar("voz", e, (st.session_state.get("user") or {}).get("id"))
        return {**respuesta, "audio": None, "error": "sin voz natural"}


# ---------------------------------------------------------------------------------------------------------------
# Componentes (se ejecutan en la página)
# ---------------------------------------------------------------------------------------------------------------
_JS_COMUN = r"""
const PREF = (k, defecto = null) => { try { const v = localStorage.getItem("practic_voz_" + k); return v === null ? defecto : v; } catch (e) { return defecto; } };
const GUARDAR = (k, v) => { try { localStorage.setItem("practic_voz_" + k, v); } catch (e) {} };
const hayVozNavegador = () => !!window.speechSynthesis;
const vocesEspanol = () => (hayVozNavegador() ? speechSynthesis.getVoices() : [])
  .filter(v => (v.lang || "").toLowerCase().startsWith("es"));
const rango = v => {
  const l = (v.lang || "").toLowerCase();
  return (l === "es-mx" ? 0 : l === "es-us" || l === "es-419" ? 1 : 2) + (/natural|online|neural|premium|enhanced/i.test(v.name) ? 0 : 3);
};
// Preferencia: "" = automática (voz natural del servidor), "natural:<voz>" o el nombre de una voz del navegador
const vozNatural = () => { const p = PREF("voz2", ""); return p === "" ? "" : p.startsWith("natural:") ? p.slice(8) : null; };
const elegirVozNavegador = () => {
  const voces = vocesEspanol();
  return voces.find(v => v.name === PREF("voz2")) || voces.sort((a, b) => rango(a) - rango(b))[0] || null;
};
const trozos = texto => {
  const salida = [];
  for (const f of (texto.match(/[^.!?;:]+[.!?;:]*/g) || [texto])) {
    const frase = f.trim();
    if (!frase) continue;
    if (salida.length && (salida[salida.length - 1] + " " + frase).length < 180) salida[salida.length - 1] += " " + frase;
    else salida.push(frase);
  }
  return salida;
};
// Un solo lector suena a la vez en toda la página. Con la voz natural, el audio llega por trozos: suena el primero
// mientras el servidor prepara el siguiente (así empieza a hablar en un par de segundos aunque la respuesta sea larga).
const ESTADO = window.__practicVoz || (window.__practicVoz = { clave: null, audio: null, token: null, cache: {} });
ESTADO.cache = ESTADO.cache || {};
const avisar = () => window.dispatchEvent(new Event("practic-voz"));
const navegadorHablando = () => hayVozNavegador() && (speechSynthesis.speaking || speechSynthesis.pending);
const callarTodo = () => {
  if (ESTADO.audio) { ESTADO.audio.onended = null; ESTADO.audio.pause(); }
  if (hayVozNavegador()) speechSynthesis.cancel();
  ESTADO.clave = null; ESTADO.audio = null; ESTADO.token = null; ESTADO.cola = null;
};
const terminar = clave => { if (ESTADO.clave === clave) { ESTADO.clave = null; ESTADO.audio = null; ESTADO.token = null; avisar(); } };
const decirNavegador = (texto, clave) => {
  if (!hayVozNavegador()) return terminar(clave);
  callarTodo();
  ESTADO.clave = clave;
  const go = () => {
    if (ESTADO.clave !== clave) return;
    const voz = elegirVozNavegador();
    const partes = trozos(texto);
    partes.forEach((t, i) => {
      const u = new SpeechSynthesisUtterance(t);
      u.lang = voz ? voz.lang : "es-MX";
      if (voz) u.voice = voz;
      u.rate = parseFloat(PREF("velocidad", "1")) || 1;
      if (i === partes.length - 1) u.onend = u.onerror = () => terminar(clave);
      speechSynthesis.speak(u);
    });
    avisar();
  };
  if (speechSynthesis.getVoices().length) go();
  else { let hecho = false; const una = () => { if (!hecho) { hecho = true; go(); } };
         speechSynthesis.addEventListener("voiceschanged", una, { once: true }); setTimeout(una, 1200); }
};
const activo = clave => ESTADO.clave === clave && (!!ESTADO.audio || !!ESTADO.token || !!ESTADO.cola || navegadorHablando());
const cargando = clave => ESTADO.clave === clave && !ESTADO.audio && !navegadorHablando() && (!!ESTADO.token || !!ESTADO.cola);
const enPausa = () => ESTADO.audio ? ESTADO.audio.paused : hayVozNavegador() && speechSynthesis.paused;
const pausarOSeguir = () => {
  if (ESTADO.audio) { if (ESTADO.audio.paused) ESTADO.audio.play(); else ESTADO.audio.pause(); }
  else if (navegadorHablando()) { if (speechSynthesis.paused) speechSynthesis.resume(); else speechSynthesis.pause(); }
  avisar(); setTimeout(avisar, 200);  // el navegador marca la pausa un instante después
};
const pedirParte = i => {
  ESTADO.token = Date.now() + "-" + i;
  ESTADO.disparar("pedir", { ...ESTADO.pedido, i, t: ESTADO.token });
  avisar();
};
const pedirSiguiente = () => {  // prepara el siguiente trozo que falte, de uno en uno
  const c = ESTADO.cola && ESTADO.cache[ESTADO.cola.id];
  if (!c || ESTADO.token || c.total === null) return;
  for (let j = ESTADO.cola.idx + 1; j < c.total; j++) if (!c.partes[j]) return pedirParte(j);
};
const tocarParte = (i, clave) => {
  const c = ESTADO.cache[ESTADO.cola.id];
  ESTADO.cola.idx = i;
  const audio = new Audio("data:audio/mpeg;base64," + c.partes[i]);
  ESTADO.audio = audio;
  audio.onended = () => {
    if (ESTADO.clave !== clave) return;
    ESTADO.audio = null;
    const sig = i + 1;
    if (c.total !== null && sig >= c.total) { ESTADO.cola = null; return terminar(clave); }
    if (c.partes[sig]) return tocarParte(sig, clave);
    ESTADO.cola.idx = sig;  // el siguiente aún no llega: se espera (la etiqueta dice «Preparando la voz…»)
    if (!ESTADO.token) pedirParte(sig);
    avisar();
  };
  audio.play().catch(() => { ESTADO.cola = null; terminar(clave); });
  pedirSiguiente();
  avisar();
};
// Escuchar: voz natural del servidor por trozos o, si se eligió una del navegador (o no hay servidor), la del navegador
const pedirOHablar = (data, setTriggerValue, clave) => {
  const voz = vozNatural();
  const velocidad = PREF("velocidad", "1");
  if (voz === null || !data.servidor) return decirNavegador(data.texto, clave);
  callarTodo();
  const elegida = voz || data.voz_defecto;
  const id = clave + "|" + elegida + "|" + velocidad;
  ESTADO.clave = clave;
  ESTADO.disparar = setTriggerValue;
  ESTADO.pedido = { voz: elegida, velocidad };
  ESTADO.cache[id] = ESTADO.cache[id] || { partes: [], total: null };
  ESTADO.cola = { id, idx: 0, texto: data.texto };
  if (ESTADO.cache[id].partes[0]) tocarParte(0, clave); else pedirParte(0);
};
// Llega un trozo pedido: se guarda y suena si es el que toca (si falló al principio, habla la voz del navegador)
const recibir = (data, setTriggerValue, clave) => {
  if (ESTADO.clave !== clave) return;
  ESTADO.disparar = setTriggerValue;
  if (!data.token || data.token !== ESTADO.token) return;
  ESTADO.token = null;
  const c = ESTADO.cola && ESTADO.cache[ESTADO.cola.id];
  if (!c) return;
  if (!data.audio) {
    if (!ESTADO.audio && !c.partes.length) { const texto = ESTADO.cola.texto; ESTADO.cola = null; return decirNavegador(texto, clave); }
    c.total = c.partes.length;  // falló a la mitad: se termina con lo que ya sonó
    if (!ESTADO.audio) { ESTADO.cola = null; terminar(clave); }
    return;
  }
  c.partes[data.i] = data.audio;
  c.total = data.total;
  if (!ESTADO.audio && ESTADO.cola.idx === data.i) tocarParte(data.i, clave); else pedirSiguiente();
  avisar();
};
"""

_LECTOR = st.components.v2.component(
    "practic_lector_voz",
    html="""<div class="barra" hidden>
  <button class="escuchar" type="button" title="Leer en voz alta">
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 10v4h4l5 4V6L7 10H3zm13.5 2a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/></svg>
    <span class="txt">Escuchar</span>
  </button>
  <button class="detener" type="button" title="Dejar de leer" hidden>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h10v10H7z"/></svg><span>Detener</span>
  </button>
</div>""",
    css="""
.barra { display: flex; gap: 6px; margin-top: 4px; }
button { display: inline-flex; align-items: center; gap: 5px; font: inherit; font-size: 0.8rem; color: inherit;
  background: transparent; border: 1px solid rgba(127, 127, 127, 0.35); border-radius: 8px; padding: 3px 10px;
  cursor: pointer; opacity: 0.85; transition: background 0.15s, opacity 0.15s; }
button:hover { background: rgba(127, 127, 127, 0.12); opacity: 1; }
button.activo { border-color: #2563eb; color: #2563eb; opacity: 1; }
svg { width: 15px; height: 15px; fill: currentColor; }
""",
    js=_JS_COMUN + r"""
export default function ({ parentElement, data, setTriggerValue }) {
  const barra = parentElement.querySelector(".barra");
  const escuchar = parentElement.querySelector(".escuchar");
  const etiqueta = parentElement.querySelector(".txt");
  const detener = parentElement.querySelector(".detener");
  const clave = data.clave;
  barra.hidden = false;
  const pintar = () => {
    const mio = activo(clave);
    etiqueta.textContent = cargando(clave) ? "Preparando la voz…" : !mio ? "Escuchar" : enPausa() ? "Continuar" : "Pausar";
    escuchar.classList.toggle("activo", mio);
    detener.hidden = !mio;
  };
  escuchar.onclick = () => {
    if (cargando(clave)) return;
    if (activo(clave)) pausarOSeguir(); else pedirOHablar(data, setTriggerValue, clave);
  };
  detener.onclick = () => { callarTodo(); avisar(); };
  window.addEventListener("practic-voz", pintar);
  recibir(data, setTriggerValue, clave);
  pintar();
  if (data.forzar || (data.auto && PREF("auto") === "1")) {
    let leidos = [];
    try { leidos = JSON.parse(sessionStorage.getItem("practic_voz_leidos") || "[]"); } catch (e) {}
    if (!leidos.includes(clave)) {
      leidos.push(clave);
      try { sessionStorage.setItem("practic_voz_leidos", JSON.stringify(leidos.slice(-50))); } catch (e) {}
      pedirOHablar(data, setTriggerValue, clave);
    }
  }
  return () => window.removeEventListener("practic-voz", pintar);
}
""",
)

_AJUSTES = st.components.v2.component(
    "practic_ajustes_voz",
    html="""<div class="panel">
  <label class="fila"><input type="checkbox" class="auto"> Leer en voz alta las respuestas nuevas del tutor</label>
  <label class="campo">Voz<select class="voz"></select></label>
  <label class="campo">Velocidad
    <select class="velocidad">
      <option value="0.8">Lenta</option><option value="1">Normal</option><option value="1.2">Rápida</option>
    </select>
  </label>
  <button type="button" class="probar">Probar la voz</button>
  <p class="nota"></p>
</div>""",
    css="""
.panel { font-size: 0.92rem; color: inherit; }
.fila { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; cursor: pointer; }
.campo { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; font-size: 0.85rem; }
select { font: inherit; color: inherit; background: transparent; border: 1px solid rgba(127, 127, 127, 0.35);
  border-radius: 8px; padding: 6px 8px; }
select option, select optgroup { color: #111; }
button { font: inherit; color: inherit; background: transparent; border: 1px solid rgba(127, 127, 127, 0.35);
  border-radius: 8px; padding: 6px 12px; cursor: pointer; }
button:hover { background: rgba(127, 127, 127, 0.12); }
.nota { font-size: 0.8rem; opacity: 0.75; margin: 8px 0 0; }
""",
    js=_JS_COMUN + r"""
export default function ({ parentElement, data, setTriggerValue }) {
  const $ = s => parentElement.querySelector(s);
  const auto = $(".auto"), voz = $(".voz"), velocidad = $(".velocidad"), nota = $(".nota"), probar = $(".probar");
  auto.checked = PREF("auto") === "1";
  velocidad.value = PREF("velocidad", "1");
  const opcion = (padre, valor, texto) => { const o = document.createElement("option"); o.value = valor; o.textContent = texto; padre.appendChild(o); };
  const llenar = () => {
    voz.innerHTML = "";
    if (data.servidor) {
      opcion(voz, "", "Automática (" + data.voces[data.voz_defecto] + ")");
      const g = document.createElement("optgroup"); g.label = "Voces naturales (necesitan internet)";
      for (const [id, nombre] of Object.entries(data.voces)) opcion(g, "natural:" + id, nombre);
      voz.appendChild(g);
    } else {
      opcion(voz, "", "Automática (la mejor del navegador)");
    }
    const voces = vocesEspanol().sort((a, b) => rango(a) - rango(b));
    if (voces.length) {
      const g = document.createElement("optgroup"); g.label = "Voces de este navegador";
      for (const v of voces) opcion(g, v.name, v.name + " (" + v.lang + ")");
      voz.appendChild(g);
    }
    const actual = PREF("voz2", "");
    voz.value = [...voz.options].some(o => o.value === actual) ? actual : "";
    nota.textContent = "Las voces naturales suenan casi humanas y se oyen igual en cualquier dispositivo. "
      + "La elección se guarda en este navegador.";
  };
  llenar();
  if (hayVozNavegador()) speechSynthesis.addEventListener("voiceschanged", llenar);
  auto.onchange = () => GUARDAR("auto", auto.checked ? "1" : "0");
  voz.onchange = () => GUARDAR("voz2", voz.value);
  velocidad.onchange = () => GUARDAR("velocidad", velocidad.value);
  const pintar = () => {
    probar.textContent = cargando("prueba") ? "Preparando la voz…" : activo("prueba") ? "Detener" : "Probar la voz";
  };
  probar.onclick = () => {
    if (activo("prueba")) { callarTodo(); avisar(); return; }
    pedirOHablar(data, setTriggerValue, "prueba");
  };
  window.addEventListener("practic-voz", pintar);
  recibir(data, setTriggerValue, "prueba");
  pintar();
  return () => {
    window.removeEventListener("practic-voz", pintar);
    if (hayVozNavegador()) speechSynthesis.removeEventListener("voiceschanged", llenar);
  };
}
""",
)

_PRUEBA = "Hola, soy tu tutor de PRACTIC_APP. Así sonarán mis explicaciones."


def _datos_base(texto: str, clave: str) -> dict:
    datos = {"texto": texto, "clave": clave, "servidor": True, "voces": VOCES_NATURALES,
             "voz_defecto": VOZ_NATURAL_DEFECTO}
    guardado = st.session_state.get("_voz_audios", {}).get(clave)
    if guardado:
        datos.update(guardado)
    return datos


def _guardar_audio(clave: str, texto: str, pedido: dict) -> None:
    respuesta = _audio_para(texto, pedido)
    respuesta.update(voz=pedido.get("voz"), velocidad=str(pedido.get("velocidad") or "1"))
    audios = st.session_state.setdefault("_voz_audios", {})
    audios.pop(clave, None)
    audios[clave] = respuesta
    while len(audios) > _AUDIOS_GUARDADOS:  # los más viejos se tiran para no llenar la memoria de la sesión
        audios.pop(next(iter(audios)))


@st.fragment
def _lector(texto: str, clave: str, auto: bool, forzar: bool) -> None:
    # Dentro de un fragmento: al pedir el audio solo se vuelve a dibujar este botón, no toda la pantalla
    resultado = _LECTOR(data={**_datos_base(texto, clave), "auto": bool(auto), "forzar": bool(forzar)}, key=f"voz_{clave}",
                        on_pedir_change=lambda: None)
    pedido = getattr(resultado, "pedir", None)
    if pedido:
        _guardar_audio(clave, texto, pedido)
        st.rerun(scope="fragment")


def lector(markdown: str, clave: str, auto: bool = False, forzar: bool = False) -> None:
    """Botones «Escuchar» y «Detener» para un mensaje. `auto`: es una respuesta nueva (se lee sola si así se eligió)."""
    texto = texto_para_leer(markdown)
    if texto:
        _lector(texto, clave, auto, forzar)


@st.fragment
def ajustes() -> None:
    """Panel para elegir voz, velocidad y lectura automática (se guardan en el navegador)."""
    resultado = _AJUSTES(data=_datos_base(_PRUEBA, "prueba"), key="ajustes_voz", on_pedir_change=lambda: None)
    pedido = getattr(resultado, "pedir", None)
    if pedido:
        _guardar_audio("prueba", _PRUEBA, pedido)
        st.rerun(scope="fragment")
