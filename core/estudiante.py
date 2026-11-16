"""Animación de carga: un libro abierto que pasa sus páginas mientras suben destellos y símbolos de estudio.

Es un SVG con animaciones CSS, sin imágenes ni librerías. Se dibuja con `cargando(...)`, que muestra el indicador de
Streamlit y, debajo, el libro mientras se espera la respuesta de la IA (preguntas, ejercicios, explicaciones).

Cómo está hecha:
- Tres páginas giran sobre el lomo una tras otra (cada una tarda 1,5 s y van desfasadas un tercio de ciclo, así que
  siempre hay una pasando). Al girar se encogen en horizontal y se curvan un poco, como una hoja de verdad; al caer
  del otro lado se desvanecen y la siguiente ya viene en camino, sin saltos.
- El libro «respira» (sube y baja unos píxeles) y su sombra se estira con él.
- Formas sencillas (estrella, cruz, anillo, rombo) suben desde las páginas, se desvanecen y vuelven a empezar.
Los colores salen de las variables del tema, así que funciona en claro y en oscuro. Con «reducir movimiento» queda
una pose fija (libro abierto con una página a medio girar).
"""
import math
import random
from contextlib import contextmanager

import streamlit as st

from core import cargas

CICLO = 1.5          # segundos que tarda una página en pasar
PAGINAS = 3          # páginas girando a la vez, desfasadas
MUESTRAS = 60        # fotogramas del ciclo de una página
SALIDA, LLEGADA = .08, .52   # fracción del ciclo en que la página empieza y termina de girar


def _suave(s: float) -> float:
    s = max(0.0, min(1.0, s))
    return s * s * (3 - 2 * s)


def _pagina(p: float) -> str:
    """Declaraciones CSS de la página en la fracción p (0–1) de su ciclo."""
    giro = _suave((p - SALIDA) / (LLEGADA - SALIDA))
    ancho = math.cos(math.pi * giro)             # 1 = abierta a la derecha, -1 = caída a la izquierda
    curva = -9 * math.sin(math.pi * giro)        # el borde exterior se levanta a mitad del giro
    opacidad = min(1.0, p / .05) if p < .05 else (1 - max(0.0, (p - .82) / .13) if p > .82 else 1.0)
    return f"transform:skewY({curva:.2f}deg) scaleX({ancho:.3f});opacity:{max(0.0, opacidad):.3f}"


def _css() -> str:
    cuadros = "".join(f"{100 * i / MUESTRAS:.2f}%{{{_pagina(i / MUESTRAS)}}}" for i in range(MUESTRAS + 1))
    return f"@keyframes est-pagina{{{cuadros}}}" + """
.tu-est{display:flex;justify-content:center;padding:6px 0 0;pointer-events:none}
.tu-est svg{width:min(300px,84%);height:auto;overflow:visible;fill:none;stroke:var(--tu-tinta);stroke-width:2.6;
stroke-linecap:round;stroke-linejoin:round}
.tu-est .est-respira{animation:est-respira 3s ease-in-out infinite}
.tu-est .est-sombra{fill:var(--tu-tinta);stroke:none;opacity:.12;transform-origin:110px 122px;animation:est-sombra 3s ease-in-out infinite}
.tu-est .est-tapa{fill:var(--est-mochila)}
.tu-est .est-papel{fill:var(--est-papel)}
.tu-est .est-linea{stroke-width:2.2;opacity:.28}
.tu-est .est-hoja{fill:var(--est-papel);animation:est-pagina 1.5s linear infinite}
.tu-est .est-hoja.p2{animation-delay:-1s}
.tu-est .est-hoja.p3{animation-delay:-.5s}
.tu-est .est-marca{fill:#F59E0B;stroke:var(--tu-tinta);stroke-width:2}
.tu-est .est-sube{animation:est-sube 3.2s ease-out var(--d) infinite;opacity:0}
.tu-est .est-sube .rel{fill:currentColor;stroke:none}
.tu-est .est-sube .hue{stroke:currentColor;stroke-width:2.6;fill:none}
@keyframes est-respira{50%{transform:translateY(-2.5px)}}
@keyframes est-sombra{50%{transform:scaleX(.93);opacity:.08}}
@keyframes est-sube{0%{opacity:0;transform:translate(0,4px) scale(.4)}18%{opacity:1}100%{opacity:0;transform:translate(var(--dx),-46px) scale(1.1) rotate(var(--r))}}
"""


CSS_ESTUDIANTE = _css() + cargas.CSS


def _libro() -> str:
    """HTML (una sola línea) del libro animado. Sin texto de usuario: es seguro insertarlo tal cual."""
    lineas = "".join(f'<path class="est-linea" d="M{x1} {y}H{x2}"/>' for y in (46, 58, 70, 82, 94)
                     for x1, x2 in ((54, 102 - (y % 3) * 6), (120, 166 - (y % 4) * 5)))
    # Hojas que giran sobre el lomo (x = 0 es el lomo): ocupan la mitad derecha y caen sobre la izquierda
    hojas = "".join(f'<g transform="translate(110 0)"><g class="est-hoja p{n}">'
                    f'<path d="M0 28H60Q64 28 64 32V100Q64 104 60 104H0Z"/>'
                    f'<path class="est-linea" d="M10 46H54M10 58H48M10 70H54M10 82H46"/></g></g>' for n in range(1, PAGINAS + 1))
    estrella = '<path class="rel" d="M0 -5C.8 -1.6 1.6 -.8 5 0C1.6 .8 .8 1.6 0 5C-.8 1.6 -1.6 .8 -5 0C-1.6 -.8 -.8 -1.6 0 -5Z"/>'
    particulas = [
        (84, "#F59E0B", -10, "-20deg", "0s", estrella),
        (132, "#10B981", 12, "25deg", ".7s", '<path class="hue" d="M0 -4V4M-4 0H4"/>'),
        (104, "#F472B6", -4, "0deg", "1.4s", '<circle class="hue" r="3.6"/>'),
        (152, "#38BDF8", 6, "-25deg", "2.1s", '<path class="rel" d="M0 -5L4.5 0L0 5L-4.5 0Z"/>'),
        (66, "#38BDF8", -6, "20deg", "2.6s", '<path class="hue" d="M0 -4V4M-4 0H4"/>'),
    ]
    sube = "".join(f'<g transform="translate({x} 22)"><g class="est-sube" style="--dx:{dx}px;--r:{r};--d:{d};color:{c}">{f}</g></g>'
                   for x, c, dx, r, d, f in particulas)
    return ('<div class="tu-est" role="img" aria-label="Un libro abierto pasa sus páginas">'
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 128" aria-hidden="true">'
            '<ellipse class="est-sombra" cx="110" cy="122" rx="62" ry="4.5"/>'
            '<g class="est-respira">'
            '<rect class="est-tapa" x="38" y="22" width="144" height="92" rx="8"/>'
            '<path class="est-papel" d="M50 28H110V104H50Q46 104 46 100V32Q46 28 50 28Z"/>'
            '<path class="est-papel" d="M110 28H170Q174 28 174 32V100Q174 104 170 104H110Z"/>'
            f'{lineas}{hojas}'
            '<path d="M110 28V104"/>'
            '<path class="est-marca" d="M104 26V52L108 48L112 52V26Z"/>'
            '</g>'
            f'{sube}</svg></div>')


VARIANTES = {"libro": _libro, **cargas.VARIANTES}


def estudiante_html(nombre: str | None = None) -> str:
    """HTML de una animación de carga: la que se pide por nombre o, si no, una al azar."""
    return VARIANTES[nombre or random.choice(list(VARIANTES))]()


def elegir(ultima: str | None = None) -> str:
    """Nombre de una animación al azar, distinta de la última que se mostró."""
    return random.choice([n for n in VARIANTES if n != ultima])


@contextmanager
def cargando(mensaje: str):
    """Como `st.spinner(mensaje)`, pero con una animación debajo (distinta cada vez) mientras dura la espera."""
    nombre = elegir(st.session_state.get("_ultima_carga"))
    st.session_state["_ultima_carga"] = nombre
    with st.spinner(mensaje):
        lugar = st.empty()
        lugar.markdown(estudiante_html(nombre), unsafe_allow_html=True)
        try:
            yield
        finally:
            lugar.empty()
