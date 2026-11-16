"""Animaciones de carga (además del libro de `core/estudiante.py`): SVG con CSS, sin imágenes ni librerías.

Cada variante es una función que devuelve el HTML de una sola línea. `core/estudiante.py` elige una al azar cada vez
(sin repetir la anterior) y las muestra debajo del indicador de carga de Streamlit.
Los colores salen de las variables del tema (`--tu-tinta`, `--est-mochila`, `--est-papel`), así que funcionan en claro
y en oscuro. Los movimientos que dependen de una trayectoria (la punta del lápiz, la lupa, los electrones...) se
calculan aquí en Python y se escriben como fotogramas, así todo empalma sin saltos al reiniciar el ciclo.
Con «reducir movimiento» cada una queda en una pose fija completa.
"""
import bisect
import math

AZUL, VERDE, AMBAR, ROSA, CIELO = "var(--est-mochila)", "#10B981", "#F59E0B", "#F472B6", "#38BDF8"
ESTRELLA = "M0 -5C.8 -1.6 1.6 -.8 5 0C1.6 .8 .8 1.6 0 5C-.8 1.6 -1.6 .8 -5 0C-1.6 -.8 -.8 -1.6 0 -5Z"


def envolver(interior: str, etiqueta: str) -> str:
    return (f'<div class="tu-est" role="img" aria-label="{etiqueta}">'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 128" aria-hidden="true">{interior}</svg></div>')


def _kf(nombre: str, filas: list[tuple[float, str]]) -> str:
    return f"@keyframes {nombre}{{" + "".join(f"{p:.2f}%{{{d}}}" for p, d in filas) + "}"


def _muestras(nombre: str, funcion, n: int = 48) -> str:
    return _kf(nombre, [(100 * i / n, funcion(i / n)) for i in range(n + 1)])


def _suave(s: float) -> float:
    s = max(0.0, min(1.0, s))
    return s * s * (3 - 2 * s)


def _fundido(p: float, entra: float = .04, sale: float = .92) -> float:
    """Opacidad que aparece al empezar el ciclo y se apaga al terminar (0 en ambos extremos)."""
    if p < entra:
        return p / entra
    return 1.0 if p <= sale else max(0.0, (1 - p) / (1 - sale))


# ---------------------------------------------------------------------------------------------------------------
# 1. Lápiz que escribe
# ---------------------------------------------------------------------------------------------------------------
_TRAZO = [(52 + 112 * i / 80, 92 + 5 * math.sin(i / 80 * 2 * math.pi * 5)) for i in range(81)]
_ACUM = [0.0]
for _a, _b in zip(_TRAZO, _TRAZO[1:]):
    _ACUM.append(_ACUM[-1] + math.hypot(_b[0] - _a[0], _b[1] - _a[1]))


def _punta(s: float) -> tuple[float, float]:
    """Punto del trazo a la fracción s (0–1) de su longitud."""
    d = s * _ACUM[-1]
    i = min(max(bisect.bisect_left(_ACUM, d), 1), len(_ACUM) - 1)
    t = (d - _ACUM[i - 1]) / ((_ACUM[i] - _ACUM[i - 1]) or 1)
    (x0, y0), (x1, y1) = _TRAZO[i - 1], _TRAZO[i]
    return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t


def _lapiz() -> str:
    trazo = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in _TRAZO)
    x, y = _TRAZO[-1]
    return envolver(
        '<rect class="c-papel" x="34" y="22" width="152" height="92" rx="8"/>'
        '<path class="c-regla" d="M46 46H174M46 62H174M46 78H174"/>'
        '<path class="c-regla" d="M60 22V114" style="stroke:#F472B6"/>'
        f'<path class="c-trazo" pathLength="100" d="{trazo}"/>'
        f'<g class="c-lapiz" transform="translate({x:.1f} {y:.1f})"><g transform="rotate(35)">'
        '<path d="M0 0L-3.6 -9H3.6Z" fill="#F5D0A0"/><path d="M-1.1 -3.3H1.1" stroke="var(--tu-tinta)"/>'
        '<rect x="-3.6" y="-34" width="7.2" height="25" fill="#F59E0B"/>'
        '<rect x="-3.6" y="-38" width="7.2" height="4" fill="#CBD5E1"/>'
        '<path d="M-3.6 -38V-41Q0 -45 3.6 -41V-38Z" fill="#F472B6"/></g></g>', "Un lápiz escribe sobre una hoja")


def _css_lapiz() -> str:
    def p(t):
        return _punta(min(1.0, t / .8))
    return (_muestras("c-escribe", lambda t: "transform:translate({:.1f}px,{:.1f}px);opacity:{:.3f}".format(*p(t), _fundido(t)), 60)
            + _muestras("c-tinta", lambda t: f"stroke-dashoffset:{100 * (1 - min(1.0, t / .8)):.2f};opacity:{_fundido(t, .001):.3f}", 60)
            + """
.tu-est .c-papel{fill:var(--est-papel)}
.tu-est .c-regla{stroke-width:2;opacity:.22}
.tu-est .c-trazo{stroke:var(--est-mochila);stroke-width:3;stroke-dasharray:100;animation:c-tinta 3.2s linear infinite}
.tu-est .c-lapiz{animation:c-escribe 3.2s linear infinite}
.tu-est .c-lapiz rect,.tu-est .c-lapiz path{stroke-width:2}
""")


# ---------------------------------------------------------------------------------------------------------------
# 2. Birrete que se lanza y se atrapa
# ---------------------------------------------------------------------------------------------------------------
def _vuelo(t: float) -> tuple[float, float, float]:
    """(altura en px, giro en grados, volteo vertical) del birrete: sube, da dos vueltas de campana y cae."""
    if t >= .85:
        return 0.0, 0.0, 1.0
    q = t / .85
    return (-52 * 4 * q * (1 - q)) or 0.0, (14 * math.sin(2 * math.pi * q)) or 0.0, math.cos(4 * math.pi * q)


def _birrete() -> str:
    chispas = "".join(f'<g transform="translate({x} {y}) scale({e})"><path class="c-chispa" d="{ESTRELLA}" style="animation-delay:{d}s"/></g>'
                      for x, y, e, d in ((76, 90, 1, 0), (146, 82, 1.2, .04), (110, 62, .8, .08)))
    return envolver(
        '<ellipse class="c-sombra" cx="110" cy="118" rx="26" ry="4.5"/>'
        '<g transform="translate(110 86)"><g class="c-birrete">'
        f'<path d="M-15 5V16Q0 23 15 16V5" fill="{AZUL}"/><path d="M-27 0L0 -13L27 0L0 13Z" fill="{AZUL}"/>'
        f'<path d="M21 1V17" stroke="{AMBAR}"/><circle cx="21" cy="19.5" r="3" fill="{AMBAR}" stroke="none"/></g></g>'
        + chispas, "Un birrete de graduación se lanza al aire")


def _css_birrete() -> str:
    return (_muestras("c-vuelo", lambda t: "transform:translateY({:.2f}px) rotate({:.2f}deg) scaleY({:.3f})".format(
        _vuelo(t)[0], _vuelo(t)[1], _vuelo(t)[2]))
            + _muestras("c-sombra", lambda t: f"transform:scaleX({1 + _vuelo(t)[0] / 130:.3f});opacity:{.16 + _vuelo(t)[0] / 600:.3f}")
            + """
.tu-est .c-birrete{animation:c-vuelo 2.4s linear infinite}
.tu-est .c-birrete path{stroke-width:2.4}
.tu-est .c-sombra{fill:var(--tu-tinta);stroke:none;opacity:.16;transform-origin:110px 118px;animation:c-sombra 2.4s linear infinite}
.tu-est .c-chispa{fill:#F59E0B;stroke:none;opacity:0;animation:c-chispa 2.4s ease-out infinite}
@keyframes c-chispa{0%,84%{opacity:0;transform:scale(.3)}90%{opacity:1;transform:scale(1)}100%{opacity:0;transform:scale(1.3)}}
""")


# ---------------------------------------------------------------------------------------------------------------
# 3. Libros que se apilan
# ---------------------------------------------------------------------------------------------------------------
_PILA = [(64, AZUL), (54, AMBAR), (58, VERDE), (46, ROSA)]


def _pila() -> str:
    libros = ""
    for i, (ancho, color) in enumerate(_PILA):
        base = 108 - 15 * i
        libros += (f'<g transform="translate(110 {base})"><g class="c-libro l{i}">'
                   f'<rect x="{-ancho / 2}" y="-14" width="{ancho}" height="14" rx="3" fill="{color}"/>'
                   f'<path class="c-lomo" d="M{-ancho / 2 + 9} -10V-4M{-ancho / 2 + 14} -10V-4"/></g></g>')
    return envolver('<ellipse class="c-sombra-f" cx="110" cy="110" rx="46" ry="3.5"/>' + libros, "Una pila de libros que va creciendo")


def _css_pila() -> str:
    salida = ""
    for i in range(len(_PILA)):
        t0 = .06 + .15 * i
        filas = [(0, "opacity:0;transform:translateY(-70px) scaleY(1)"), (100 * t0, "opacity:0;transform:translateY(-70px) scaleY(1)"),
                 (100 * (t0 + .02), "opacity:1;transform:translateY(-62px) scaleY(1)"),
                 (100 * (t0 + .09), "opacity:1;transform:translateY(0) scaleY(1)"),
                 (100 * (t0 + .105), "opacity:1;transform:translateY(0) scaleY(.86)"),
                 (100 * (t0 + .13), "opacity:1;transform:translateY(0) scaleY(1)"),
                 (88, "opacity:1;transform:translateY(0) scaleY(1)"), (97, "opacity:0;transform:translateY(0) scaleY(1)"),
                 (100, "opacity:0;transform:translateY(-70px) scaleY(1)")]
        salida += _kf(f"c-cae{i}", filas) + f".tu-est .c-libro.l{i}{{animation:c-cae{i} 3.6s ease-in infinite}}"
    return salida + """
.tu-est .c-libro rect{stroke-width:2.2}
.tu-est .c-lomo{stroke-width:2;opacity:.5}
.tu-est .c-sombra-f{fill:var(--tu-tinta);stroke:none;opacity:.12}
"""


# ---------------------------------------------------------------------------------------------------------------
# 4. Lupa que lee
# ---------------------------------------------------------------------------------------------------------------
_RUTA_LUPA = [(62, 46), (150, 46), (66, 62), (150, 62), (66, 78), (150, 78), (62, 94), (150, 94), (62, 46)]


def _posicion_lupa(t: float) -> tuple[float, float]:
    n = len(_RUTA_LUPA) - 1
    i = min(int(t * n), n - 1)
    e = _suave(t * n - i)
    (x0, y0), (x1, y1) = _RUTA_LUPA[i], _RUTA_LUPA[i + 1]
    return x0 + (x1 - x0) * e, y0 + (y1 - y0) * e


def _lupa() -> str:
    lineas = "".join(f'<path class="c-texto" d="M54 {y}H{ancho}"/>' for y, ancho in ((46, 168), (62, 150), (78, 164), (94, 140)))
    return envolver(
        '<rect class="c-papel" x="34" y="26" width="152" height="82" rx="8"/>' + lineas +
        '<g class="c-lupa" transform="translate(150 94)"><circle r="15" fill="#F59E0B" fill-opacity=".18" stroke="var(--est-mochila)" stroke-width="3.6"/>'
        '<path d="M-8 -5Q-6 -10 0 -11" stroke="#fff" stroke-width="2.4" opacity=".8"/><path d="M10.6 10.6L24 24" stroke-width="6"/></g>',
        "Una lupa recorre un texto")


def _css_lupa() -> str:
    return (_muestras("c-lee", lambda t: "transform:translate({:.1f}px,{:.1f}px)".format(*_posicion_lupa(t)), 96)
            + """
.tu-est .c-papel{fill:var(--est-papel)}
.tu-est .c-texto{stroke-width:3;opacity:.25}
.tu-est .c-lupa{animation:c-lee 5s linear infinite}
""")


# ---------------------------------------------------------------------------------------------------------------
# 5. Bombilla que se enciende
# ---------------------------------------------------------------------------------------------------------------
def _bombilla() -> str:
    rayos = "".join(f'<path class="c-rayo" style="animation-delay:{i * .05}s" d="M{110 + 40 * math.cos(math.radians(a)):.1f} '
                    f'{50 + 40 * math.sin(math.radians(a)):.1f}L{110 + 52 * math.cos(math.radians(a)):.1f} {50 + 52 * math.sin(math.radians(a)):.1f}"/>'
                    for i, a in enumerate(range(-180, 1, 30)))
    return envolver(
        '<circle class="c-halo" cx="110" cy="50" r="34"/>' + rayos +
        '<g transform="translate(110 52) scale(3.6) translate(-12 -12)"><path class="c-vidrio" d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>'
        '<path class="c-base" d="M9 18h6M10 22h4M9.5 14.5h5"/></g>'
        '<path class="c-filamento" d="M103 55L107 47L110 55L113 47L117 55"/>', "Una bombilla se enciende")


def _css_bombilla() -> str:
    patron = [(0, .06), (18, .06), (22, .95), (28, .3), (34, 1), (80, 1), (94, .06), (100, .06)]
    return (_kf("c-luz", [(p, f"fill-opacity:{v}") for p, v in patron])
            + _kf("c-rayos", [(p, f"opacity:{v}") for p, v in patron])
            + _kf("c-aureola", [(p, f"opacity:{v * .22:.3f}") for p, v in patron])
            + """
.tu-est .c-vidrio{stroke-width:.8;fill:#F59E0B;fill-opacity:.95;animation:c-luz 2.6s ease-in-out infinite}
.tu-est .c-base{stroke-width:.8}
.tu-est .c-rayo{stroke:#F59E0B;stroke-width:3;opacity:1;animation:c-rayos 2.6s ease-in-out infinite}
.tu-est .c-halo{fill:#F59E0B;stroke:none;opacity:.22;animation:c-aureola 2.6s ease-in-out infinite}
.tu-est .c-filamento{stroke:var(--tu-tinta);stroke-width:1.8;opacity:.7}
""")


# ---------------------------------------------------------------------------------------------------------------
# 6. Engranes que piensan
# ---------------------------------------------------------------------------------------------------------------
def _engrane(cx: float, cy: float, giro: float, color: str, sentido: str) -> str:
    return (f'<g transform="translate({cx} {cy})"><g class="c-engrane {sentido}"><g transform="rotate({giro})">'
            f'<circle class="c-dientes" r="22" pathLength="20" stroke-dasharray="1 1" stroke-width="7" stroke="{color}"/>'
            f'<circle r="19" fill="var(--est-papel)"/><circle r="6" fill="{color}" stroke="none"/>'
            f'<path d="M-12 0H12M0 -12V12" stroke="{color}" stroke-width="3"/></g></g></g>')


def _engranes() -> str:
    # Mismo número de dientes, giros opuestos y fase calculada para que el diente de uno entre en el hueco del otro
    ang = math.degrees(math.atan2(14, 41))
    return envolver(_engrane(88, 58, ang - 9, AZUL, "a") + _engrane(129, 72, ang + 9, AMBAR, "b"),
                    "Dos engranes giran juntos")


def _css_engranes() -> str:
    return """
.tu-est .c-engrane{animation:c-gira 6s linear infinite}
.tu-est .c-engrane.b{animation-name:c-gira-inv}
.tu-est .c-dientes{stroke-linecap:butt}
@keyframes c-gira{to{transform:rotate(360deg)}}
@keyframes c-gira-inv{to{transform:rotate(-360deg)}}
"""


# ---------------------------------------------------------------------------------------------------------------
# 7. Barras que suben y bajan
# ---------------------------------------------------------------------------------------------------------------
def _barras() -> str:
    colores = (AZUL, VERDE, AMBAR, ROSA, CIELO, AZUL)
    barras = "".join(f'<g transform="translate({46 + 25 * i} 106)"><rect class="c-barra" style="--d:{i * .16}s" x="0" y="-74" width="14" '
                     f'height="74" rx="4" fill="{c}"/></g>' for i, c in enumerate(colores))
    return envolver('<path class="c-suelo" d="M34 108H188"/>' + barras, "Barras de una gráfica que suben y bajan")


def _css_barras() -> str:
    return """
.tu-est .c-barra{stroke-width:2.2;animation:c-sube 1.7s ease-in-out var(--d) infinite}
.tu-est .c-suelo{stroke-width:2.4;opacity:.4}
@keyframes c-sube{0%,100%{transform:scaleY(.28)}50%{transform:scaleY(1)}}
"""


# ---------------------------------------------------------------------------------------------------------------
# 8. Lista de tareas que se va marcando
# ---------------------------------------------------------------------------------------------------------------
def _lista() -> str:
    filas = ""
    for i, (y, color) in enumerate(((38, VERDE), (66, AZUL), (94, AMBAR))):
        filas += (f'<g transform="translate(52 {y})"><g class="c-fila">'
                  f'<rect x="0" y="-10" width="20" height="20" rx="6" fill="var(--est-papel)"/>'
                  f'<path class="c-marca k{i}" pathLength="16" d="M5 0l4.5 4.5L16 -4.5" stroke="{color}" stroke-width="3.4"/>'
                  f'<g transform="translate(32 0)"><path class="c-renglon r{i}" d="M0 0H86" stroke-width="5"/></g></g></g>')
    return envolver(filas, "Una lista de tareas se va marcando")


def _css_lista() -> str:
    salida = _kf("c-fila", [(0, "opacity:0"), (5, "opacity:1"), (88, "opacity:1"), (97, "opacity:0"), (100, "opacity:0")])
    for i in range(3):
        t0 = 8 + 24 * i
        salida += _kf(f"c-marca{i}", [(0, "stroke-dashoffset:16"), (t0, "stroke-dashoffset:16"), (t0 + 8, "stroke-dashoffset:0"), (100, "stroke-dashoffset:0")])
        salida += _kf(f"c-renglon{i}", [(0, "transform:scaleX(0)"), (t0 + 3, "transform:scaleX(0)"), (t0 + 16, "transform:scaleX(1)"), (100, "transform:scaleX(1)")])
        salida += (f".tu-est .c-marca.k{i}{{animation:c-marca{i} 4s ease-out infinite}}"
                   f".tu-est .c-renglon.r{i}{{animation:c-renglon{i} 4s ease-out infinite}}")
    return salida + """
.tu-est .c-fila{animation:c-fila 4s linear infinite}
.tu-est .c-fila rect{stroke-width:2.4}
.tu-est .c-marca{stroke-dasharray:16;fill:none}
.tu-est .c-renglon{opacity:.35}
"""


# ---------------------------------------------------------------------------------------------------------------
# 9. Cohete que despega
# ---------------------------------------------------------------------------------------------------------------
def _cohete() -> str:
    estrellas = "".join(f'<circle class="c-estrella" style="animation-delay:{-d}s;animation-duration:{t}s" cx="{x}" cy="0" r="{r}"/>'
                        for x, d, t, r in ((26, .2, 1.9, 1.8), (52, 1.1, 1.5, 1.4), (164, .6, 1.7, 2), (192, 1.3, 2.1, 1.5),
                                           (38, 1.6, 1.8, 1.2), (180, .1, 1.6, 1.3), (70, .9, 2.0, 1.6), (150, 1.5, 1.4, 1.2)))
    return envolver(
        f'{estrellas}<g transform="translate(110 58)"><g class="c-cohete">'
        '<g transform="translate(0 14)"><path class="c-llama" d="M-5.5 0Q0 28 5.5 0Z"/></g>'
        f'<path d="M-9 4L-19 19L-9 14Z" fill="{AMBAR}"/><path d="M9 4L19 19L9 14Z" fill="{AMBAR}"/>'
        '<path d="M0 -34C12 -22 12 0 8 14H-8C-12 0 -12 -22 0 -34Z" fill="var(--est-papel)"/>'
        f'<path d="M0 -34C5 -29 8 -25 9 -20H-9C-8 -25 -5 -29 0 -34Z" fill="{AZUL}"/>'
        f'<circle cy="-6" r="5.4" fill="{CIELO}"/></g></g>', "Un cohete despega entre las estrellas")


def _css_cohete() -> str:
    return (_muestras("c-vibra", lambda t: f"transform:translateY({2.6 * math.sin(2 * math.pi * t):.2f}px) rotate({1.6 * math.sin(4 * math.pi * t):.2f}deg)", 24)
            + """
.tu-est .c-cohete{animation:c-vibra 1.2s linear infinite}
.tu-est .c-cohete path,.tu-est .c-cohete circle{stroke-width:2.4}
.tu-est .c-llama{fill:#F59E0B;stroke:none;transform-origin:0 0;animation:c-llama .35s ease-in-out infinite alternate}
.tu-est .c-estrella{fill:var(--tu-tinta);stroke:none;opacity:0;animation:c-cae-e 1.8s linear infinite}
@keyframes c-llama{from{transform:scaleY(.7)}to{transform:scaleY(1.15)}}
@keyframes c-cae-e{0%{opacity:0;transform:translateY(0)}10%{opacity:.55}90%{opacity:.55}100%{opacity:0;transform:translateY(128px)}}
""")


# ---------------------------------------------------------------------------------------------------------------
# 10. Átomo con electrones
# ---------------------------------------------------------------------------------------------------------------
def _atomo() -> str:
    orbitas = "".join(f'<g transform="rotate({k})"><ellipse class="c-orbita" rx="52" ry="18"/>'
                      f'<circle class="c-electron" style="animation-delay:{-i * .8}s" r="4.6" fill="{c}"/></g>'
                      for i, (k, c) in enumerate(((0, AMBAR), (60, VERDE), (120, ROSA))))
    return envolver(f'<g transform="translate(110 64)">{orbitas}<g class="c-nucleo">'
                    f'<circle cx="-2.6" cy="-1.6" r="4.6" fill="{AZUL}"/><circle cx="3" cy="-1.2" r="4.6" fill="{CIELO}"/>'
                    f'<circle cx="0" cy="3.4" r="4.6" fill="{AMBAR}"/></g></g>', "Un átomo con electrones en órbita")


def _css_atomo() -> str:
    return (_muestras("c-orbita", lambda t: f"transform:translate({52 * math.cos(2 * math.pi * t):.2f}px,{18 * math.sin(2 * math.pi * t):.2f}px)")
            + """
.tu-est .c-orbita{opacity:.35;stroke-width:2}
.tu-est .c-electron{stroke:none;animation:c-orbita 2.4s linear infinite}
.tu-est .c-nucleo{animation:c-late 1.2s ease-in-out infinite}
.tu-est .c-nucleo circle{stroke-width:2}
@keyframes c-late{50%{transform:scale(1.18)}}
""")


VARIANTES = {
    "lapiz": _lapiz, "birrete": _birrete, "pila": _pila, "lupa": _lupa, "bombilla": _bombilla, "engranes": _engranes,
    "barras": _barras, "lista": _lista, "cohete": _cohete, "atomo": _atomo,
}

CSS = "".join(f() for f in (_css_lapiz, _css_birrete, _css_pila, _css_lupa, _css_bombilla, _css_engranes, _css_barras,
                            _css_lista, _css_cohete, _css_atomo))
