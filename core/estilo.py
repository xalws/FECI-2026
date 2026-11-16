"""Identidad visual de la aplicación: paleta, íconos, hoja de estilos y componentes de presentación.

Toda la apariencia vive aquí y en .streamlit/config.toml (colores y tipografía del tema). Las pantallas solo
llaman a estas funciones (encabezado, titulo, datos, anillo, lista...) y no repiten CSS.
Todo texto que viene del usuario o de la base de datos se escapa antes de insertarlo en HTML.
"""
import html
import random
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

ZONA_POR_DEFECTO = "America/Ciudad_Juarez"

# Interruptor de las animaciones «llamativas» (entradas, rebotes, conteos, confeti). Con False la app queda
# con las transiciones básicas. El navegador también las apaga solo si el usuario pidió «reducir movimiento».
ANIMACIONES = True

# (color del ícono/acento, fondo suave)
TONOS = {
    "indigo": ("#0B3D91", "#EAF1FC"),
    "violeta": ("#1F63C9", "#EAF1FC"),
    "cielo": ("#0284C7", "#E0F2FE"),
    "verde": ("#059669", "#ECFDF5"),
    "ambar": ("#D97706", "#FFFBEB"),
    "rojo": ("#DC2626", "#FEF2F2"),
    "rosa": ("#DB2777", "#FDF2F8"),
}

# Íconos de línea (estilo Lucide). Incluye los que ya usaban las pantallas para no cambiar su aspecto.
ICONOS = {
    "award": '<circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/>',
    "book": '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/>',
    "bulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/>',
    "cap": '<path d="M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z"/><path d="M22 10v6"/><path d="M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "circle": '<circle cx="12" cy="12" r="10"/>',
    "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
    "history": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
    "key": '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
    "layers": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "link": '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "message": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "sparkles": '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "trending": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "user_plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "x": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "zap": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
}


TONOS_OSCURO = {"indigo": "#6EA0F0", "violeta": "#8DB6F5", "cielo": "#38BDF8", "verde": "#34D399", "ambar": "#FBBF24",
                "rojo": "#F87171", "rosa": "#F472B6"}


def _tono(nombre: str) -> tuple[str, str]:
    """(color, fondo suave) del tono, más claro cuando el tema es oscuro."""
    color, fondo = TONOS.get(nombre, TONOS["indigo"])
    return (TONOS_OSCURO.get(nombre, color), fondo) if es_oscuro() else (color, fondo)


def _e(texto) -> str:
    return html.escape(str(texto), quote=True)


def svg(nombre: str, tam: int = 22, color: str = "currentColor", grosor: float = 2) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tam}" height="{tam}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{grosor}" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONOS.get(nombre, ICONOS["circle"])}</svg>')


def _html(contenido: str) -> None:
    # Una sola línea: el procesador de Markdown no debe convertir sangrías en bloques de código
    st.markdown(contenido, unsafe_allow_html=True)


# Enteros que no son la parte decimal de un número ni el denominador de una fracción («8.5/10» anima solo el 8)
_ENTERO = re.compile(r"(?<![\d.,/])\d+")


def con_conteo(valor) -> str:
    """HTML del valor con cada número entero listo para «contar» desde 0 al aparecer.

    «1 h 35 min» anima el 1 y el 35; «45.0%» anima el 45 y deja fijo «.0%». El número real queda en el texto,
    así que se lee igual aunque el navegador no anime (o las animaciones estén apagadas).
    """
    texto, partes, pos = str(valor), [], 0
    for m in _ENTERO.finditer(texto):
        n = m.group()
        if (len(n) > 1 and n[0] == "0") or len(n) > 7:  # «05» perdería su cero; los muy largos no se animan
            continue
        partes.append(_e(texto[pos:m.start()]))
        partes.append(f'<span class="tu-num" style="--tu-n:{int(n)}"><b>{n}</b></span>')
        pos = m.end()
    partes.append(_e(texto[pos:]))
    return "".join(partes)


# ---------------------------------------------------------------------------------------------------------------
# Componentes
# ---------------------------------------------------------------------------------------------------------------
def titulo(icono: str, texto: str, nivel: int = 3) -> None:
    """Título de sección con ícono (misma firma que usaban las pantallas)."""
    if nivel == 1:
        encabezado(texto, icono=icono)
        return
    tam = 20 if nivel >= 3 else 22
    _html(f'<div class="tit tit-{nivel}"><span class="tit-icono">{svg(icono, tam)}</span>'
          f'<h{nivel}>{_e(texto)}</h{nivel}></div>')


def encabezado(titulo: str, subtitulo: str = "", icono: str = "book", chips=(), compacto: bool = False) -> None:
    """Encabezado principal de cada pantalla, con degradado animado.

    `chips`: textos cortos, o pares (ícono, texto), que se muestran como etiquetas bajo el título.
    """
    etiquetas = []
    for chip in chips:
        if not chip:
            continue
        icono_chip, texto = chip if isinstance(chip, tuple) else (None, chip)
        etiquetas.append(f'<span class="tu-chip">{svg(icono_chip, 14) if icono_chip else ""}{_e(texto)}</span>')
    sub = f'<div class="tu-hero-sub">{_e(subtitulo)}</div>' if subtitulo else ""
    fila_chips = f'<div class="tu-chips">{"".join(etiquetas)}</div>' if etiquetas else ""
    _html(f'<div class="tu-hero{" tu-hero-compacto" if compacto else ""}"><i class="tu-hero-brillo"></i>'
          f'<div class="tu-hero-fila">'
          f'<div class="tu-hero-icono">{svg(icono, 26)}</div><div class="tu-hero-textos">'
          f'<div class="tu-hero-titulo" role="heading" aria-level="1">{_e(titulo)}</div>{sub}</div></div>'
          f'{fila_chips}</div>')


def datos(items: list[dict]) -> None:
    """Tarjetas de datos que se acomodan solas al ancho (no recortan el texto como st.metric en columnas).

    Cada item: {"icono", "etiqueta", "valor", "detalle" (opcional), "tono" (opcional)}.
    """
    tarjetas = []
    for i, d in enumerate(items):
        color, fondo = _tono(d.get("tono", "indigo"))
        detalle = f'<div class="tu-dato-detalle">{_e(d["detalle"])}</div>' if d.get("detalle") else ""
        tarjetas.append(
            f'<div class="tu-dato" style="--color:{color};--fondo:{fondo};animation-delay:{i * 0.08:.2f}s">'
            f'<div class="tu-dato-cab"><span class="tu-dato-icono">{svg(d.get("icono", "circle"), 19)}</span>'
            f'<span class="tu-dato-etiqueta">{_e(d["etiqueta"])}</span></div>'
            f'<div class="tu-dato-valor">{con_conteo(d["valor"])}</div>{detalle}</div>')
    _html(f'<div class="tu-datos">{"".join(tarjetas)}</div>')


def insignia(texto: str, tono: str = "indigo", icono: str | None = None) -> str:
    color, fondo = _tono(tono)
    return (f'<span class="tu-insignia" style="--color:{color};--fondo:{fondo}">'
            f'{svg(icono, 13) if icono else ""}{_e(texto)}</span>')


def anillo(porcentaje: float, titulo: str, detalle: str = "", etiqueta: str = "", tono: str = "indigo") -> None:
    """Tarjeta con un anillo de avance (0 a 100) y su explicación."""
    p = max(0, min(100, round(porcentaje)))
    extra = insignia(etiqueta, tono, "award") if etiqueta else ""
    _html(f'<div class="tu-anillo-tarjeta"><div class="tu-anillo" style="--tu-p:{p}">'
          f'<div class="tu-anillo-centro"><span>{con_conteo(p)}%</span><small>avance</small></div></div>'
          f'<div class="tu-anillo-textos"><div class="tu-anillo-titulo">{_e(titulo)}</div>{extra}'
          f'<div class="tu-anillo-detalle">{_e(detalle)}</div></div></div>')


def lista(items: list[dict]) -> None:
    """Lista de tarjetas con acento de color. Cada item: {"icono", "titulo", "sub", "texto", "tono"}."""
    filas = []
    for i, it in enumerate(items):
        color, fondo = _tono(it.get("tono", "indigo"))
        sub = f'<div class="tu-item-sub">{_e(it["sub"])}</div>' if it.get("sub") else ""
        texto = f'<div class="tu-item-texto">{_e(it["texto"])}</div>' if it.get("texto") else ""
        filas.append(f'<div class="tu-item" style="--color:{color};--fondo:{fondo};animation-delay:{i * 0.07:.2f}s">'
                     f'<span class="tu-item-icono">{svg(it.get("icono", "circle"), 19)}</span>'
                     f'<div><div class="tu-item-titulo">{_e(it["titulo"])}</div>{sub}{texto}</div></div>')
    _html(f'<div class="tu-lista">{"".join(filas)}</div>')


def calendario_actividad(filas: list[list[dict]], meta: int, hoy) -> None:
    """Calendario de semanas (lunes a domingo): más oscuro cuanto más se estudió; el borde marca el día de hoy."""
    cabecera = "".join(f'<span class="tu-cal-dia">{d}</span>' for d in "LMMJVSD")
    celdas = []
    for fila in filas:
        for c in fila:
            m = c["minutos"]
            nivel = 0 if m <= 0 else (1 if m < meta * 0.5 else (2 if m < meta else 3))
            clases = f"tu-cal-celda n{nivel}" + (" futuro" if c["futuro"] else "") + (" hoy" if c["fecha"] == hoy else "")
            texto = "" if c["futuro"] else f"{c['fecha']:%d/%m}: {round(m)} min"
            celdas.append(f'<span class="{clases}" title="{_e(texto)}"></span>')
    leyenda = ('<div class="tu-cal-leyenda"><span>Menos</span><i class="tu-cal-celda n0"></i><i class="tu-cal-celda n1"></i>'
               '<i class="tu-cal-celda n2"></i><i class="tu-cal-celda n3"></i><span>Meta cumplida</span></div>')
    _html(f'<div class="tu-cal-tarjeta"><div class="tu-cal">{cabecera}{"".join(celdas)}</div>{leyenda}</div>')


NOMBRES_MEDALLA = ["Sin conseguir", "Bronce", "Plata", "Élite", "Oro"]


def medalla(logro: dict, tam: int = 64, retraso: float = 0.0) -> str:
    """Medalla de un logro: bronce, plata, élite (color de su categoría) u oro (con brillo animado). Nivel 0 = gris."""
    color, fondo = _tono(logro["tono"])
    nivel = logro["nivel"]
    return (f'<span class="tu-med n{nivel}" style="--tam:{tam}px;--color:{color};--fondo:{fondo};animation-delay:{retraso:.2f}s" '
            f'title="{_e(logro["titulo"])} · {NOMBRES_MEDALLA[nivel]}"><span class="tu-med-aro">'
            f'<span class="tu-med-disco">{svg(logro["icono"], 24)}</span></span></span>')


def _pasos(logro: dict) -> str:
    return "".join(f'<i class="p n{n}{" on" if logro["nivel"] >= n else ""}" title="{NOMBRES_MEDALLA[n]}"></i>' for n in (1, 2, 3, 4))


def logros_grid(items: list[dict]) -> None:
    """Tarjetas de logros con su medalla, su avance hacia el siguiente nivel y los 4 niveles posibles."""
    tarjetas = []
    for i, l in enumerate(items):
        color, fondo = _tono(l["tono"])
        if l["siguiente"] is None:
            pie = '<div class="tu-lg-pie oro">¡Nivel máximo!</div>'
        else:
            pie = f'<div class="tu-lg-pie">{l["valor"]} de {l["siguiente"]}</div>'
        nivel = NOMBRES_MEDALLA[l["nivel"]]
        tarjetas.append(
            f'<div class="tu-lg n{l["nivel"]}" style="--color:{color};--fondo:{fondo};animation-delay:{min(i, 10) * 0.04:.2f}s">'
            f'{medalla(l, 68, min(i, 10) * 0.04)}<div class="tu-lg-textos"><div class="tu-lg-titulo">{_e(l["titulo"])}</div>'
            f'<div class="tu-lg-nivel">{nivel}</div><div class="tu-lg-desc">{_e(l["descripcion"])}</div>'
            f'<div class="tu-lg-barra"><i style="width:{l["avance"]}%"></i></div>{pie}'
            f'<div class="tu-lg-pasos">{_pasos(l)}</div></div></div>')
    _html(f'<div class="tu-lgs">{"".join(tarjetas)}</div>')


def vitrina(items: list[dict], vacio: str = "Todavía no hay logros para mostrar.") -> None:
    """Fila de medallas grandes (los logros que el alumno eligió mostrar)."""
    if not items:
        st.caption(vacio)
        return
    cuerpo = "".join(f'<div class="tu-vit">{medalla(l, 84, i * 0.08)}<b>{_e(l["titulo"])}</b>'
                     f'<span class="n{l["nivel"]}">{NOMBRES_MEDALLA[l["nivel"]]}</span></div>' for i, l in enumerate(items))
    _html(f'<div class="tu-vitrina">{cuerpo}</div>')


def posicion_html(n: int) -> str:
    """Insignia con la posición en el ranking: oro, plata y bronce para los tres primeros."""
    return f'<span class="tu-pos p{n if n <= 3 else 0}">{n}</span>'


def fila_ranking(nombre: str, detalle: str, xp: int, yo: bool = False) -> str:
    """Nombre, título y XP de un alumno en el ranking (el botón «Ver perfil» lo pone la pantalla al lado)."""
    etiqueta = ' <span class="tu-yo">Tú</span>' if yo else ""
    return (f'<div class="tu-rank{" yo" if yo else ""}"><div class="tu-rank-nombre">{_e(nombre)}{etiqueta}</div>'
            f'<div class="tu-rank-det">{_e(detalle)}</div><div class="tu-rank-xp"><b>{xp}</b> XP</div></div>')


def grafica_xp_semanal(filas: list[dict]) -> None:
    """Área con los XP ganados cada semana (8 semanas); `filas` trae «semana» (fecha) y «xp»."""
    import altair as alt
    import pandas as pd

    df = pd.DataFrame(filas)
    df["etiqueta"] = pd.to_datetime(df["semana"]).dt.strftime("%d/%m")
    color = TONOS["indigo"][0]
    relleno = alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                           stops=[alt.GradientStop(color="rgba(11,61,145,0.02)", offset=0),
                                  alt.GradientStop(color="rgba(11,61,145,0.38)", offset=1)])
    base = alt.Chart(df).encode(
        x=alt.X("etiqueta:O", sort=None, title="Semana (lunes)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("xp:Q", title="XP", scale=alt.Scale(domainMin=0)),
        tooltip=[alt.Tooltip("etiqueta:O", title="Semana del"), alt.Tooltip("xp:Q", title="XP")])
    capas = (base.mark_area(line={"color": color, "strokeWidth": 2.5}, color=relleno, interpolate="monotone")
             + base.mark_point(filled=True, size=80, color=color))
    st.altair_chart(capas.properties(height=220), width="stretch")


def grafica_barras(df, categoria: str, valor: str, titulo_valor: str, maximo: float | None = None,
                   color_por: str | None = None, colores: dict | None = None) -> None:
    """Barras horizontales que muestran el nombre completo de cada categoría (st.bar_chart lo recorta)."""
    import altair as alt

    eje_x = {"title": titulo_valor, "axis": alt.Axis(tickCount=5)}
    if maximo:
        eje_x["scale"] = alt.Scale(domain=[0, maximo])
    if color_por and colores:
        color = alt.Color(f"{color_por}:N", title=None, legend=alt.Legend(orient="bottom"),
                          scale=alt.Scale(domain=list(colores), range=list(colores.values())))
    else:
        color = alt.value(TONOS["indigo"][0])
    grafica = (alt.Chart(df).mark_bar(cornerRadiusEnd=6)
               .encode(x=alt.X(f"{valor}:Q", **eje_x),
                       y=alt.Y(f"{categoria}:N", title=None, sort="-x", axis=alt.Axis(labelLimit=230)),
                       color=color,
                       tooltip=[alt.Tooltip(f"{categoria}:N", title=categoria.capitalize()),
                                alt.Tooltip(f"{valor}:Q", title=titulo_valor)])
               .properties(height=alt.Step(34)))
    st.altair_chart(grafica, width="stretch")


def grafica_fechas(df, fecha: str, valor: str, titulo_valor: str) -> None:
    """Área con puntos por día, con fechas en formato día/mes."""
    import altair as alt

    color = TONOS["indigo"][0]
    relleno = alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                           stops=[alt.GradientStop(color="rgba(11,61,145,0.02)", offset=0),
                                  alt.GradientStop(color="rgba(11,61,145,0.32)", offset=1)])
    base = alt.Chart(df).encode(
        x=alt.X(f"{fecha}:T", title=None, axis=alt.Axis(format="%d/%m", labelAngle=0, tickCount="day")),
        y=alt.Y(f"{valor}:Q", title=titulo_valor),
        tooltip=[alt.Tooltip(f"{fecha}:T", title="Fecha", format="%d/%m/%Y"),
                 alt.Tooltip(f"{valor}:Q", title=titulo_valor)])
    capas = (base.mark_area(line={"color": color, "strokeWidth": 2.5}, color=relleno, interpolate="monotone")
             + base.mark_point(filled=True, size=70, color=color))
    st.altair_chart(capas.properties(height=260), width="stretch")


def iniciales(nombre: str) -> str:
    partes = [p for p in nombre.replace(".", " ").split() if p[:1].isalpha()]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def tarjeta_usuario(user: dict) -> None:
    """Tarjeta del usuario en el menú lateral: iniciales, nombre y rol."""
    roles = {"alumno": "Alumno", "maestro": "Maestro", "admin": "Administrador"}
    rol = user.get("rol", "")
    st.markdown(
        f'<div class="tu-usuario"><div class="tu-avatar">{_e(iniciales(user.get("nombre", "")))}</div>'
        f'<div class="tu-usuario-datos"><div class="tu-usuario-nombre">{_e(user.get("nombre", ""))}</div>'
        f'<span class="tu-rol tu-rol-{_e(rol)}">{_e(roles.get(rol, rol))}</span></div></div>',
        unsafe_allow_html=True)


def saludo(nombre: str = "") -> str:
    """«Buenos días / Buenas tardes / Buenas noches» según la hora del navegador del usuario."""
    try:
        zona = ZoneInfo(st.context.timezone or ZONA_POR_DEFECTO)
    except Exception:
        zona = ZoneInfo(ZONA_POR_DEFECTO)
    hora = datetime.now(zona).hour
    parte = "Buenos días" if 5 <= hora < 12 else ("Buenas tardes" if 12 <= hora < 19 else "Buenas noches")
    primero = next((p for p in nombre.split() if p[:1].isalpha() and not p.endswith(".")), "")
    return f"{parte}, {primero}" if primero else parte


def zona_horaria() -> ZoneInfo:
    try:
        return ZoneInfo(st.context.timezone or ZONA_POR_DEFECTO)
    except Exception:
        return ZoneInfo(ZONA_POR_DEFECTO)


def fecha_local(fecha: datetime) -> datetime:
    """Convierte una fecha guardada en UTC a la hora del navegador del usuario."""
    if fecha.tzinfo is None:  # SQLite la devuelve sin zona
        fecha = fecha.replace(tzinfo=timezone.utc)
    return fecha.astimezone(zona_horaria())


def insignias(*items: tuple) -> None:
    """Fila de insignias; cada item es (texto, tono, ícono)."""
    _html(f'<div class="tu-insignias">{"".join(insignia(*it) for it in items)}</div>')


def marca_acceso() -> None:
    """Panel de presentación de la pantalla de inicio de sesión."""
    rasgos = [("message", "Un tutor siempre disponible",
               "Responde con el material de tu materia y te dice de qué página sale."),
              ("target", "Exámenes que se adaptan a ti",
               "Suben de dificultad mientras aciertas y bajan si te cuesta."),
              ("trending", "Tu avance, claro y visible",
               "Niveles por tema, unidad y materia, según la retícula oficial.")]
    filas = "".join(f'<div class="tu-rasgo"><span class="tu-rasgo-icono">{svg(i, 20)}</span>'
                    f'<div><b>{_e(t)}</b><span>{_e(d)}</span></div></div>' for i, t, d in rasgos)
    _html(f'<div class="tu-acceso-hero"><div class="tu-acceso-marca"><span class="tu-acceso-logo">'
          f'{svg("cap", 30)}</span><div><div class="tu-acceso-nombre">Tutor Universitario</div>'
          f'<div class="tu-acceso-lema">Estudia a tu ritmo, con tu propio material</div></div></div>'
          f'<div class="tu-acceso-titulo">Aprende con un tutor que conoce tu clase</div>'
          f'<div class="tu-acceso-texto">Pregunta, practica y mide tu avance con el contenido que sube tu '
          f'maestro, sin distracciones.</div><div class="tu-rasgos">{filas}</div></div>')


# ---------------------------------------------------------------------------------------------------------------
# Hoja de estilos
# ---------------------------------------------------------------------------------------------------------------
CSS = """
:root{--tu-indigo:#0B3D91;--tu-violeta:#1F63C9;--tu-cielo:#0EA5E9;--tu-tinta:#0B1F44;--tu-gris:#64748B;
--tu-borde:#DCE5F3;--tu-suave:#EAF1FC;--tu-degradado:linear-gradient(135deg,#0B3D91 0%,#1F63C9 100%);
--tu-sombra:0 1px 2px rgba(11,31,68,.05),0 6px 20px rgba(11,31,68,.06);
--tu-sombra-alta:0 2px 6px rgba(11,31,68,.07),0 16px 34px rgba(11,31,68,.11);
--tu-lateral:#0A1B3D;--tu-texto:#334155;--tu-sup:#fff;--tu-pista:#DEE7F5;--tu-burbuja:linear-gradient(135deg,#EAF1FC,#EAF1FC);}
[style*="--fondo"]{--fondo:color-mix(in srgb,var(--color) 13%,transparent)!important}
@keyframes tu-aparecer{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes tu-degradado{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes tu-flotar{0%,100%{transform:translate(0,0)}50%{transform:translate(-10px,12px)}}
@keyframes tu-latido{0%,100%{box-shadow:0 0 0 0 rgba(11,61,145,.35)}50%{box-shadow:0 0 0 8px rgba(11,61,145,0)}}

/* Lienzo general */
[data-testid="stMainBlockContainer"]{max-width:1180px;padding-top:3.6rem;padding-bottom:4rem}
[data-testid="stHeader"]{background:rgba(246,247,251,.78);backdrop-filter:blur(10px)}
[data-testid="stAppDeployButton"]{display:none}
hr{border-color:var(--tu-borde)!important}
[data-testid="stSidebar"] hr{border-color:rgba(157,187,240,.16)!important;margin:1.1rem 0!important}

/* Encabezado principal */
.tu-hero{position:relative;overflow:hidden;border-radius:22px;padding:26px 30px;margin:0 0 1.3rem;color:#fff;
background:#0B3D91;
box-shadow:0 20px 44px -22px rgba(11,61,145,.65)}
.tu-hero-fila{position:relative;z-index:1;display:flex;align-items:center;gap:16px}
.tu-hero-icono{width:54px;height:54px;flex-shrink:0;border-radius:16px;display:flex;align-items:center;justify-content:center;
background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);backdrop-filter:blur(6px);color:#fff}
.tu-hero-titulo{font-family:"Plus Jakarta Sans",sans-serif;font-size:1.85rem;font-weight:800;line-height:1.15;letter-spacing:-.01em;color:#fff}
.tu-hero-sub{margin-top:4px;font-size:1rem;color:rgba(255,255,255,.86)}
.tu-chips{position:relative;z-index:1;display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.tu-chip{display:inline-flex;align-items:center;gap:6px;padding:5px 12px;border-radius:999px;font-size:.82rem;font-weight:600;
background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.26);color:#fff;backdrop-filter:blur(4px)}
.tu-hero-compacto{padding:18px 24px}
.tu-hero-compacto .tu-hero-titulo{font-size:1.45rem}
.tu-hero-compacto .tu-hero-icono{width:44px;height:44px;border-radius:13px}

/* Títulos de sección con ícono */
.tit{display:flex;align-items:center;gap:.65rem;margin:1.15rem 0 .55rem}
.tit h1,.tit h2,.tit h3,.tit h4,.tit h5{margin:0!important;padding:0!important;color:var(--tu-tinta)}
.tit h3{font-size:1.18rem}.tit h4{font-size:1.04rem}
.tit-icono{width:34px;height:34px;flex-shrink:0;border-radius:10px;display:inline-flex;align-items:center;justify-content:center;
background:var(--tu-suave);color:var(--tu-indigo)}
[data-testid="stSidebar"] .tit h1,[data-testid="stSidebar"] .tit h2,[data-testid="stSidebar"] .tit h3,[data-testid="stSidebar"] .tit h4{color:#EAF1FC}
[data-testid="stSidebar"] .tit-icono{background:rgba(157,187,240,.14);color:#9DBBF0}

/* Tarjetas de datos */
.tu-datos{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:14px;margin:.2rem 0 1.2rem}
.tu-dato{background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:16px 18px;box-shadow:var(--tu-sombra);
transition:transform .18s ease,box-shadow .18s ease;animation:tu-aparecer .45s ease-out backwards}
.tu-dato:hover{transform:translateY(-3px);box-shadow:var(--tu-sombra-alta)}
.tu-dato-cab{display:flex;align-items:center;gap:10px}
.tu-dato-icono{width:36px;height:36px;border-radius:11px;display:inline-flex;align-items:center;justify-content:center;
background:var(--fondo);color:var(--color);flex-shrink:0}
.tu-dato-etiqueta{font-size:.84rem;font-weight:600;color:var(--tu-gris);line-height:1.2}
.tu-dato-valor{margin-top:12px;font-family:"Plus Jakarta Sans",sans-serif;font-size:1.7rem;font-weight:800;color:var(--tu-tinta);line-height:1.1}
.tu-dato-detalle{margin-top:4px;font-size:.78rem;color:var(--tu-gris)}

/* Insignias */
.tu-insignia{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;font-size:.78rem;font-weight:700;
background:var(--fondo);color:var(--color)}
.tu-insignias{display:flex;flex-wrap:wrap;gap:6px;margin:.15rem 0 .5rem}

/* Anillo de avance */
.tu-anillo-tarjeta{display:flex;align-items:center;gap:22px;background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:20px;
padding:18px 22px;margin:.3rem 0 1rem;box-shadow:var(--tu-sombra);animation:tu-aparecer .45s ease-out backwards}
.tu-anillo{width:104px;height:104px;flex-shrink:0;border-radius:50%;display:flex;align-items:center;justify-content:center;
background:conic-gradient(#0B3D91 0%,#1F63C9 calc(var(--tu-p)*1%),var(--tu-pista) calc(var(--tu-p)*1%))}
.tu-anillo-centro{width:80px;height:80px;border-radius:50%;background:var(--tu-sup);display:flex;flex-direction:column;align-items:center;
justify-content:center;font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:1.35rem;color:var(--tu-tinta)}
.tu-anillo-centro small{font-family:Inter,sans-serif;font-size:.62rem;font-weight:700;color:var(--tu-gris);text-transform:uppercase;letter-spacing:.08em}
.tu-anillo-titulo{font-family:"Plus Jakarta Sans",sans-serif;font-size:1.15rem;font-weight:800;color:var(--tu-tinta);margin-bottom:6px}
.tu-anillo-detalle{margin-top:8px;font-size:.88rem;color:var(--tu-gris)}

/* Lista de tarjetas con acento */
.tu-lista{display:grid;gap:10px;margin:.3rem 0 1.1rem}
.tu-item{display:flex;gap:14px;align-items:flex-start;background:var(--tu-sup);border:1px solid var(--tu-borde);border-left:4px solid var(--color);
border-radius:14px;padding:13px 16px;box-shadow:var(--tu-sombra);transition:transform .18s ease,box-shadow .18s ease;
animation:tu-aparecer .45s ease-out backwards}
.tu-item:hover{transform:translateX(4px);box-shadow:var(--tu-sombra-alta)}
.tu-item-icono{width:36px;height:36px;border-radius:11px;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;
background:var(--fondo);color:var(--color)}
.tu-item-titulo{font-weight:700;color:var(--tu-tinta);line-height:1.3}
.tu-item-sub{font-size:.78rem;font-weight:600;color:var(--color);margin-top:1px}
.tu-item-texto{font-size:.9rem;color:var(--tu-texto);margin-top:3px}

/* st.metric (pantallas que lo usan): tarjeta y sin recortar el texto */
[data-testid="stMetric"]{background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:14px 16px;
box-shadow:var(--tu-sombra);transition:transform .18s ease,box-shadow .18s ease;height:100%}
[data-testid="stMetric"]:hover{transform:translateY(-2px);box-shadow:var(--tu-sombra-alta)}
[data-testid="stMetricLabel"] .stMarkdownEllipsis,[data-testid="stMetricLabel"] p,[data-testid="stMetricValue"],[data-testid="stMetricValue"] div{
white-space:normal!important;overflow:visible!important;text-overflow:clip!important}
[data-testid="stMetricLabel"] p{color:var(--tu-gris);font-weight:600}
[data-testid="stMetricLabel"] span[role="img"]{color:var(--tu-indigo)}
[data-testid="stMetricValue"]{font-size:1.6rem;color:var(--tu-tinta);line-height:1.2}

/* Contenedores con borde como tarjetas */
[data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"][data-test-scroll-behavior]{
background:var(--tu-sup);border-radius:18px;box-shadow:var(--tu-sombra);transition:box-shadow .2s ease}
[data-testid="stMainBlockContainer"] [data-testid="stLayoutWrapper"]>[data-testid="stVerticalBlock"][data-test-scroll-behavior]:hover{box-shadow:var(--tu-sombra-alta)}
[data-testid="stMainBlockContainer"] [data-testid="stExpander"] details{background:var(--tu-sup);border-radius:16px;border-color:var(--tu-borde);
box-shadow:0 1px 2px rgba(11,31,68,.04)}
[data-testid="stMainBlockContainer"] [data-testid="stExpander"] summary:hover{color:var(--tu-indigo)}
[data-testid="stAlert"]>div{border-radius:14px}

/* Botones */
[data-testid^="stBaseButton-primary"]{background:var(--tu-degradado)!important;border:0!important;color:#fff!important;
box-shadow:0 8px 18px -8px rgba(11,61,145,.65);transition:transform .15s ease,box-shadow .15s ease,filter .15s ease}
[data-testid^="stBaseButton-primary"]:hover{transform:translateY(-1px);filter:brightness(1.07);box-shadow:0 12px 24px -10px rgba(11,61,145,.75)}
[data-testid^="stBaseButton-primary"]:active{transform:translateY(0)}
[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]{background:var(--tu-sup);border:1px solid var(--tu-borde);
color:var(--tu-tinta);transition:transform .15s ease,border-color .15s ease,color .15s ease,background .15s ease}
[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]:hover{border-color:var(--tu-violeta);color:var(--tu-violeta);
background:var(--tu-suave);transform:translateY(-1px)}
[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"]{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);color:#DCE8FB}
[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"]:hover{background:rgba(255,255,255,.12);border-color:#9DBBF0;color:#fff}

/* Pestañas */
[data-testid="stTab"] p{font-weight:600}

/* Barras de progreso */
[data-testid="stProgressBarTrack"]{background:var(--tu-pista);border-radius:999px;overflow:hidden}
[data-testid="stProgressBarTrack"]>div{background:linear-gradient(90deg,#0B3D91,#1F63C9 60%,#0EA5E9)!important;border-radius:999px;
transition:transform .9s cubic-bezier(.2,.8,.2,1)}
[data-testid="stSidebar"] [data-testid="stProgressBarTrack"]{background:rgba(255,255,255,.12)}

/* Chat */
[data-testid="stChatMessage"]{background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:.95rem 1.15rem;
box-shadow:0 1px 2px rgba(11,31,68,.05);animation:tu-aparecer .35s ease-out backwards}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){background:var(--tu-burbuja);
border-color:#C5D8F8;margin-left:min(12%,6rem);width:auto;max-width:calc(100% - min(12%,6rem))}
[data-testid="stChatMessageAvatarAssistant"]{background:var(--tu-degradado)!important;color:#fff!important;border-radius:12px!important}
[data-testid="stChatMessageAvatarUser"]{background:#0EA5E9!important;color:#fff!important;border-radius:12px!important}
[data-testid="stChatInput"]{border-radius:18px;box-shadow:var(--tu-sombra)}

/* Selectores de modo (radios con key «modo_...») como pestañas tipo píldora */
[class*="st-key-modo_"] [data-testid="stRadioGroup"]{display:inline-flex;flex-wrap:wrap;gap:.3rem;background:var(--tu-sup);border:1px solid var(--tu-borde);
border-radius:16px;padding:.35rem;box-shadow:var(--tu-sombra)}
[class*="st-key-modo_"] [data-testid="stRadioOption"]{margin:0!important;padding:.5rem .95rem;border-radius:12px;cursor:pointer;
transition:background .2s ease,box-shadow .2s ease}
[class*="st-key-modo_"] [data-testid="stRadioOption"]>div>div:first-child{display:none}
[class*="st-key-modo_"] [data-testid="stRadioOption"] p{font-weight:600}
[class*="st-key-modo_"] [data-testid="stRadioOption"]:hover{background:var(--tu-suave)}
[class*="st-key-modo_"] [data-testid="stRadioOption"][data-selected="true"]{background:var(--tu-degradado);box-shadow:0 8px 18px -8px rgba(11,61,145,.6)}
[class*="st-key-modo_"] [data-testid="stRadioOption"][data-selected="true"] p,[class*="st-key-modo_"] [data-testid="stRadioOption"][data-selected="true"] span{color:#fff!important}

/* Opciones del examen como tarjetas seleccionables */
[class*="st-key-quiz_"] [data-testid="stRadioGroup"]{gap:.6rem;width:100%}
[class*="st-key-quiz_"] [data-testid="stRadioGroup"]>div{width:100%}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]{width:100%;margin:0!important;background:var(--tu-sup);border:1.5px solid var(--tu-borde);
border-radius:14px;padding:.85rem 1rem;cursor:pointer;transition:border-color .15s ease,box-shadow .15s ease,transform .15s ease,background .15s ease}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]:hover{border-color:#9DBBF0;transform:translateY(-1px);box-shadow:var(--tu-sombra)}
[class*="st-key-quiz_"] [data-testid="stRadioOption"][data-selected="true"]{border-color:var(--tu-violeta);background:var(--tu-suave);
box-shadow:0 0 0 4px rgba(31,99,201,.16)}
[class*="st-key-quiz_"] [data-testid="stRadioOption"] p{font-size:1.02rem}

/* Menú lateral */
[data-testid="stSidebarNavLink"]{border-radius:10px;margin:2px 0;transition:background .15s ease}
[data-testid="stSidebarNavLink"]:hover{background:rgba(255,255,255,.07)}
[data-testid="stSidebarNavLink"][aria-current="page"]{background:linear-gradient(90deg,rgba(47,111,216,.38),rgba(31,99,201,.16))!important}
[data-testid="stSidebarNavLink"][aria-current="page"] p,[data-testid="stSidebarNavLink"][aria-current="page"] span{color:#fff!important;font-weight:700}
[data-testid="stNavSectionHeader"]{text-transform:uppercase;letter-spacing:.09em;font-size:.7rem!important;font-weight:700!important;color:#7FA3E0!important}
.tu-usuario{display:flex;align-items:center;gap:12px;padding:12px;border-radius:16px;background:rgba(255,255,255,.06);
border:1px solid rgba(255,255,255,.1);margin:.2rem 0 .4rem}
.tu-avatar{width:42px;height:42px;flex-shrink:0;border-radius:13px;display:flex;align-items:center;justify-content:center;
background:linear-gradient(135deg,#2F6FD8,#5B9BEF);color:#fff;font-weight:800;font-size:.95rem;}
.tu-usuario-nombre{color:#fff;font-weight:700;font-size:.95rem;line-height:1.25}
.tu-rol{display:inline-block;margin-top:3px;padding:1px 9px;border-radius:999px;font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em}
.tu-rol-alumno{background:rgba(14,165,233,.2);color:#7DD3FC}.tu-rol-maestro{background:rgba(16,185,129,.2);color:#6EE7B7}
.tu-rol-admin{background:rgba(245,158,11,.2);color:#FCD34D}

/* Medallas de logros: bronce, plata, élite (color de la categoría) y oro (con brillo) */
.tu-med{position:relative;display:inline-block;width:var(--tam,64px);height:var(--tam,64px);flex-shrink:0;border-radius:50%}
.tu-med-aro{position:absolute;inset:0;border-radius:50%;padding:calc(var(--tam,64px)*.085);background:var(--aro);box-shadow:var(--halo,none)}
.tu-med-disco{display:flex;align-items:center;justify-content:center;width:100%;height:100%;border-radius:50%;background:var(--disco);color:var(--icono);
box-shadow:inset 0 2px 6px rgba(0,0,0,.12)}
.tu-med-disco svg{width:46%;height:46%}
.tu-med.n0{--aro:linear-gradient(145deg,var(--tu-pista),var(--tu-borde));--disco:var(--tu-sup);--icono:var(--tu-gris);opacity:.7;filter:grayscale(1)}
.tu-med.n1{--aro:linear-gradient(145deg,#7C4A1E,#E8AE76 52%,#A8622B);--disco:var(--tu-sup);--icono:#A8622B;--halo:0 4px 12px -6px rgba(168,98,43,.8)}
.tu-med.n2{--aro:linear-gradient(145deg,#8793A6,#F8FAFC 50%,#94A3B8);--disco:var(--tu-sup);--icono:#64748B;--halo:0 4px 14px -6px rgba(100,116,139,.8)}
.tu-med.n3{--aro:linear-gradient(145deg,var(--color),color-mix(in srgb,var(--color) 40%,#fff) 55%,var(--color));--disco:var(--tu-sup);--icono:var(--color);
--halo:0 6px 18px -6px var(--color)}
.tu-med.n4{--aro:linear-gradient(145deg,#B7791F,#FDE68A 38%,#F59E0B 68%,#FCD34D);--disco:linear-gradient(145deg,#FFFBEB,#FDE68A);--icono:#B45309;
--halo:0 0 0 2px rgba(245,158,11,.22),0 8px 22px -6px rgba(245,158,11,.85)}
.tu-med.n4 .tu-med-aro{animation:tu-resplandor 3.2s ease-in-out infinite}
.tu-med.n4::after{content:"";position:absolute;inset:0;border-radius:50%;pointer-events:none;background:linear-gradient(115deg,transparent 38%,rgba(255,255,255,.95) 50%,transparent 62%);
background-size:260% 100%;background-position:160% 0;animation:tu-brillo-oro 3.4s ease-in-out infinite;mix-blend-mode:soft-light}
@keyframes tu-brillo-oro{0%,45%{background-position:160% 0}80%,100%{background-position:-60% 0}}
@keyframes tu-resplandor{0%,100%{box-shadow:0 0 0 2px rgba(245,158,11,.22),0 8px 22px -6px rgba(245,158,11,.75)}50%{box-shadow:0 0 0 5px rgba(245,158,11,.14),0 10px 30px -4px rgba(245,158,11,1)}}
.tu-lgs{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px;margin:.3rem 0 1.2rem}
.tu-lg{display:flex;gap:16px;align-items:center;background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:16px;box-shadow:var(--tu-sombra)}
.tu-lg.n4{border-color:#F5D77A;background:linear-gradient(135deg,var(--tu-sup),color-mix(in srgb,#FBBF24 9%,var(--tu-sup)))}
.tu-lg.n3{border-color:color-mix(in srgb,var(--color) 45%,var(--tu-borde))}
.tu-lg-textos{min-width:0;flex:1}
.tu-lg-titulo{font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;color:var(--tu-tinta);line-height:1.2}
.tu-lg-nivel{font-size:.72rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:var(--tu-gris);margin:2px 0 4px}
.tu-lg.n1 .tu-lg-nivel{color:#A8622B}.tu-lg.n2 .tu-lg-nivel{color:#64748B}.tu-lg.n3 .tu-lg-nivel{color:var(--color)}.tu-lg.n4 .tu-lg-nivel{color:#B45309}
.tu-lg-desc{font-size:.82rem;color:var(--tu-gris);line-height:1.35}
.tu-lg-barra{height:6px;border-radius:999px;background:var(--tu-pista);overflow:hidden;margin-top:8px}
.tu-lg-barra i{display:block;height:100%;border-radius:999px;background:var(--color)}
.tu-lg.n4 .tu-lg-barra i{background:linear-gradient(90deg,#F59E0B,#FDE68A)}
.tu-lg-pie{font-size:.74rem;font-weight:600;color:var(--tu-gris);margin-top:4px}.tu-lg-pie.oro{color:#B45309;font-weight:800}
.tu-lg-pasos{display:flex;gap:5px;margin-top:8px}
.tu-lg-pasos i{width:12px;height:12px;border-radius:50%;background:var(--tu-pista)}
.tu-lg-pasos i.n1.on{background:linear-gradient(145deg,#A8622B,#E8AE76)}.tu-lg-pasos i.n2.on{background:linear-gradient(145deg,#94A3B8,#F1F5F9)}
.tu-lg-pasos i.n3.on{background:var(--color)}.tu-lg-pasos i.n4.on{background:linear-gradient(145deg,#F59E0B,#FDE68A);box-shadow:0 0 6px rgba(245,158,11,.8)}
.tu-vitrina{display:flex;flex-wrap:wrap;gap:22px;justify-content:center;background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:20px;
padding:22px 18px;box-shadow:var(--tu-sombra);margin:.3rem 0 1rem}
.tu-vit{display:flex;flex-direction:column;align-items:center;gap:6px;width:112px;text-align:center}
.tu-vit b{font-size:.84rem;color:var(--tu-tinta);line-height:1.2}
.tu-vit span{font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em;color:var(--tu-gris)}
.tu-vit span.n1{color:#A8622B}.tu-vit span.n2{color:#64748B}.tu-vit span.n4{color:#B45309}
.tu-pos{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;font-weight:800;font-size:.9rem;background:var(--tu-pista);color:var(--tu-gris)}
.tu-pos.p1{background:linear-gradient(145deg,#B7791F,#FDE68A 45%,#F59E0B);color:#78350F;box-shadow:0 0 12px rgba(245,158,11,.6)}
.tu-pos.p2{background:linear-gradient(145deg,#8793A6,#F8FAFC 50%,#94A3B8);color:#334155}
.tu-pos.p3{background:linear-gradient(145deg,#7C4A1E,#E8AE76 52%,#A8622B);color:#fff}
.tu-rank{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.tu-rank-nombre{font-weight:700;color:var(--tu-tinta)}.tu-rank-det{font-size:.8rem;color:var(--tu-gris);flex:1}
.tu-rank-xp{font-size:.85rem;color:var(--tu-gris)}.tu-rank-xp b{font-size:1.05rem;color:var(--tu-tinta)}
.tu-yo{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.66rem;font-weight:800;background:var(--tu-violeta);color:#fff;vertical-align:1px}

/* Calendario de actividad y logros */
.tu-cal-tarjeta{background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:16px 18px;box-shadow:var(--tu-sombra);margin:.2rem 0 1rem}
.tu-cal{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}
.tu-cal-dia{text-align:center;font-size:.7rem;font-weight:700;color:var(--tu-gris);letter-spacing:.06em}
.tu-cal-celda{display:block;aspect-ratio:1.7;border-radius:8px;background:var(--tu-pista);min-height:18px}
.tu-cal-celda.n1{background:color-mix(in srgb,var(--tu-violeta) 38%,var(--tu-pista))}
.tu-cal-celda.n2{background:color-mix(in srgb,var(--tu-violeta) 72%,var(--tu-pista))}
.tu-cal-celda.n3{background:var(--tu-indigo)}
.tu-cal-celda.futuro{background:transparent;border:1px dashed var(--tu-borde)}
.tu-cal-celda.hoy{outline:2px solid var(--tu-violeta);outline-offset:2px}
.tu-cal-leyenda{display:flex;align-items:center;justify-content:flex-end;gap:5px;margin-top:12px;font-size:.72rem;color:var(--tu-gris)}
.tu-cal-leyenda i{width:13px;height:13px;min-height:0;border-radius:4px}
.tu-cal-leyenda span:first-child{margin-right:3px}.tu-cal-leyenda span:last-child{margin-left:3px}
.tu-logros{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:.3rem 0 1.2rem}
.tu-logro{display:flex;flex-direction:column;gap:6px;background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:16px;
box-shadow:var(--tu-sombra)}
.tu-logro-icono{width:42px;height:42px;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;background:var(--fondo);color:var(--color)}
.tu-logro-titulo{font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;color:var(--tu-tinta);margin-top:4px}
.tu-logro-texto{font-size:.82rem;color:var(--tu-gris);line-height:1.35;flex:1}
.tu-logro-ok{display:inline-flex;align-items:center;gap:5px;font-size:.78rem;font-weight:700;color:var(--color);margin-top:4px}
.tu-logro-barra{height:6px;border-radius:999px;background:var(--tu-pista);overflow:hidden;margin-top:6px}
.tu-logro-barra i{display:block;height:100%;border-radius:999px;background:var(--tu-violeta)}
.tu-logro-avance{font-size:.74rem;font-weight:600;color:var(--tu-gris)}
.tu-logro.logrado{border-color:color-mix(in srgb,var(--color) 40%,var(--tu-borde))}
.tu-logro.pendiente .tu-logro-icono{background:var(--tu-pista);color:var(--tu-gris)}
.tu-logro.pendiente .tu-logro-titulo{color:var(--tu-gris)}

/* Bloque del usuario (tarjeta, modo claro/oscuro y cerrar sesión): siempre al final del menú lateral */
[data-testid="stSidebarContent"]{display:flex;flex-direction:column}
[data-testid="stSidebarUserContent"]{flex:1 0 auto;display:flex;flex-direction:column;padding-bottom:0!important}
[data-testid="stSidebarUserContent"]>div{flex:1 0 auto;display:flex;flex-direction:column}
[data-testid="stSidebarUserContent"]>div>[data-testid="stVerticalBlock"]{flex:1 0 auto}
/* el contenedor con key queda dentro de un stLayoutWrapper: ese envoltorio es el que se ordena y se pega abajo */
[data-testid="stLayoutWrapper"]:has(>.st-key-bloque_usuario){order:99;margin-top:auto;position:sticky;bottom:0;z-index:5;background:var(--tu-lateral);border-top:1px solid rgba(157,187,240,.16);padding:.8rem 0 .9rem;box-shadow:0 -14px 16px -12px rgba(0,0,0,.5)}

/* Pantalla de inicio de sesión */
.tu-acceso-hero{position:relative;overflow:hidden;border-radius:26px;padding:38px 36px;color:#fff;min-height:520px;
background:#0B3D91;
animation:tu-aparecer .6s ease-out backwards;box-shadow:0 30px 60px -30px rgba(11,61,145,.75)}
.tu-acceso-hero>*{position:relative;z-index:1}
.tu-acceso-marca{display:flex;align-items:center;gap:14px}
.tu-acceso-logo{width:56px;height:56px;border-radius:17px;display:flex;align-items:center;justify-content:center;
background:linear-gradient(135deg,#2F6FD8,#5B9BEF);box-shadow:0 10px 24px -10px rgba(0,0,0,.5);color:#fff}
.tu-acceso-nombre{font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:1.3rem;color:#fff}
.tu-acceso-lema{font-size:.86rem;color:rgba(255,255,255,.75)}
.tu-acceso-titulo{margin-top:38px;font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:2.25rem;line-height:1.12;
letter-spacing:-.02em;color:#fff}
.tu-acceso-texto{margin-top:12px;font-size:1.02rem;color:rgba(255,255,255,.85);max-width:30rem}
.tu-rasgos{display:grid;gap:12px;margin-top:30px}
.tu-rasgo{display:flex;gap:13px;align-items:flex-start;padding:13px 14px;border-radius:16px;background:rgba(255,255,255,.09);
border:1px solid rgba(255,255,255,.14);backdrop-filter:blur(6px);transition:transform .2s ease,background .2s ease;animation:tu-aparecer .6s ease-out backwards}
.tu-rasgo:nth-child(2){animation-delay:.12s}.tu-rasgo:nth-child(3){animation-delay:.24s}
.tu-rasgo:hover{transform:translateX(4px);background:rgba(255,255,255,.14)}
.tu-rasgo b{display:block;color:#fff;font-size:.95rem}
.tu-rasgo div span{display:block;color:rgba(255,255,255,.78);font-size:.84rem;margin-top:2px}
.tu-rasgo-icono{width:42px;height:42px;flex-shrink:0;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;align-self:center;
background:rgba(255,255,255,.16);color:#fff}
.st-key-tarjeta_acceso{padding:1.7rem 1.7rem 1.3rem!important;border-radius:26px!important;box-shadow:0 24px 50px -28px rgba(11,31,68,.35)!important}
.tu-acceso-bienvenida{font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:1.6rem;color:var(--tu-tinta);margin:.2rem 0 .1rem}
.tu-acceso-ayuda{color:var(--tu-gris);font-size:.92rem;margin-bottom:.4rem}

/* Pantallas angostas y movimiento reducido */
@media (max-width:760px){.tu-hero{padding:20px}.tu-hero-titulo{font-size:1.45rem}.tu-anillo-tarjeta{flex-direction:column;align-items:flex-start}
.tu-datos{gap:10px}.tu-dato{padding:14px}.tu-dato-valor{font-size:1.45rem}
.tu-acceso-hero{min-height:auto;padding:28px 24px}.tu-acceso-titulo{font-size:1.7rem;margin-top:26px}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){margin-left:0}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
"""


CSS_OSCURO = """
:root{--tu-tinta:#E6EEFC;--tu-gris:#9FB1D3;--tu-borde:#1D3566;--tu-suave:#12295A;--tu-pista:#1D3566;
--tu-sombra:0 1px 2px rgba(0,0,0,.35),0 6px 20px rgba(0,0,0,.28);--tu-sombra-alta:0 2px 6px rgba(0,0,0,.4),0 16px 34px rgba(0,0,0,.4);
--tu-lateral:#060E1E;--tu-texto:#C3D1EA;--tu-sup:#12203F;--tu-burbuja:linear-gradient(135deg,#17315F,#1E3A70)}
[data-testid="stHeader"]{background:rgba(10,20,38,.72)!important}
"""


# ---------------------------------------------------------------------------------------------------------------
# Animaciones
# ---------------------------------------------------------------------------------------------------------------
# Fotogramas de entrada. Solo describen el inicio: el final es el estado normal del elemento, así que al terminar
# no queda ninguna transformación aplicada (una transformación residual rompería la pantalla completa de tablas
# y gráficas, que usan position:fixed, y anularía los efectos al pasar el mouse).
_FOTOGRAMAS = {
    "subir": "from{opacity:0;transform:translateY(10px)}",
    "rebote": "from{opacity:0;transform:translateY(8px) scale(.985)}",
    "pop": "from{opacity:0;transform:scale(.88)}",
    "izq": "from{opacity:0;transform:translateX(-12px)}",
    "der": "from{opacity:0;transform:translateX(12px)}",
    "voltear": "from{opacity:0;transform:translateY(8px)}",
    "contar": "from{--tu-n:0}",
    "llenar": "from{--tu-p:0}",
    "barra": "from{transform:translateX(-100%)}",
}
_APP = '[data-testid="stApp"]'
_BLOQUE = '[data-testid="stMainBlockContainer"]>[data-testid="stVerticalBlock"]'  # contenido de la pantalla

# Estilo «SaaS moderno»: movimientos cortos (150–300 ms), una sola curva de suavizado, entradas de pocos píxeles,
# elevación leve al pasar el mouse, «presionado» al hacer clic y anillos de enfoque. Nada rebota ni se repite sola.
# Ojo: dentro de <style> no puede haber un «<» seguido de letra (el saneador de st.html quitaría toda la hoja);
# por eso los tipos de @property se escriben con el escape CSS \3c en lugar de «<».
CSS_ANIMACIONES = (
    ":root{--tu-e:cubic-bezier(.2,0,0,1);--tu-e-suave:cubic-bezier(.2,0,0,1);--tu-e-rebote:cubic-bezier(.2,0,0,1);"
    "--tu-rapido:.15s;--tu-normal:.22s;--tu-lento:.45s}"
    "@property --tu-ok{syntax:'*';initial-value:1;inherits:false}"
    "@property --tu-n{syntax:'\\3c integer>';initial-value:0;inherits:false}"
    "@property --tu-p{syntax:'\\3c number>';initial-value:0;inherits:false}"
    + "".join(f"@keyframes tu-{nombre}{{{cuadros}}}" for nombre, cuadros in _FOTOGRAMAS.items())
    + """
@keyframes tu-desplegar{from{opacity:0;transform:translateY(-6px)}}
@keyframes tu-sacudir{20%,60%{transform:translateX(-4px)}40%,80%{transform:translateX(4px)}}
@keyframes tu-seleccion{0%{transform:scale(.96)}}
@keyframes tu-vibrar{0%{transform:translateX(0) rotate(0) scale(1)}10%{transform:translateX(-1px) rotate(-10deg) scale(1.12)}25%{transform:translateX(1px) rotate(8deg) scale(1.12)}40%{transform:translateX(-.5px) rotate(-6deg) scale(1.09)}55%{transform:translateX(.5px) rotate(4deg) scale(1.06)}70%{transform:rotate(-2deg) scale(1.03)}85%{transform:rotate(1deg) scale(1.01)}100%{transform:translateX(0) rotate(0) scale(1)}}
@keyframes tu-respirar{50%{opacity:.55}}
@keyframes tu-conf-x{to{transform:translateX(var(--dx))}}
@keyframes tu-conf-y{0%{opacity:1;transform:translateY(0) rotate(0);animation-timing-function:cubic-bezier(.12,.8,.3,1)}40%{opacity:1;transform:translateY(var(--up)) rotate(calc(var(--r)*.45));animation-timing-function:cubic-bezier(.6,0,.95,.55)}100%{opacity:0;transform:translateY(55vh) rotate(var(--r))}}

/* Cambio de pantalla: el contenido entra en cascada corta (los retrasos por posición se agregan abajo) */
%B>*:not(:has(.tu-confeti)){animation:tu-subir var(--tu-lento) var(--tu-e) backwards}
[data-testid="stBottomBlockContainer"]{animation:tu-subir var(--tu-lento) var(--tu-e) .15s backwards}
[data-testid="stTabPanel"]{animation:tu-subir .3s var(--tu-e) backwards}
[data-testid="stExpander"] details[open]>[data-testid="stExpanderDetails"]{animation:tu-desplegar .25s var(--tu-e)}
[data-testid="stExpander"] summary{transition:color var(--tu-rapido) var(--tu-e),background var(--tu-rapido) var(--tu-e)}

/* Encabezado: aparece sin decoración extra */
.tu-hero-brillo{display:none}
.tu-hero-icono{animation:tu-pop .35s var(--tu-e) .05s backwards}
.tu-hero-titulo{animation:tu-izq .4s var(--tu-e) .05s backwards}
.tu-hero-sub{animation:tu-izq .4s var(--tu-e) .1s backwards}
.tu-chip{animation:tu-pop .3s var(--tu-e) backwards;transition:background var(--tu-rapido) var(--tu-e),transform var(--tu-rapido) var(--tu-e)}
.tu-chip:nth-child(1){animation-delay:.15s}.tu-chip:nth-child(2){animation-delay:.2s}.tu-chip:nth-child(3){animation-delay:.25s}
.tu-chip:hover{background:rgba(255,255,255,.24);transform:scale(1.06)}

/* Títulos de sección */
.tit-icono{transition:background var(--tu-normal) var(--tu-e),color var(--tu-normal) var(--tu-e)}
.tit:hover .tit-icono{background:var(--tu-indigo);color:#fff}

/* Tarjetas de datos, anillo, listas e insignias: elevación leve y borde que se acentúa */
.tu-dato{position:relative;animation:tu-rebote .4s var(--tu-e) backwards;
transition:transform var(--tu-normal) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e),border-color var(--tu-normal) var(--tu-e)}
.tu-dato:hover{transform:translateY(-2px) scale(1.02);border-color:color-mix(in srgb,var(--color) 35%,var(--tu-borde));box-shadow:var(--tu-sombra-alta)}
.tu-dato::before,.tu-dato::after{content:none}
.tu-dato-icono,.tu-item-icono{transition:background var(--tu-normal) var(--tu-e),color var(--tu-normal) var(--tu-e)}
.tu-dato:hover .tu-dato-icono,.tu-item:hover .tu-item-icono{background:var(--color);color:#fff}
.tu-dato-valor{transition:none}
.tu-anillo-tarjeta{animation:tu-rebote .4s var(--tu-e) backwards;transition:transform var(--tu-normal) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e)}
.tu-anillo-tarjeta:hover{transform:translateY(-2px) scale(1.015);box-shadow:var(--tu-sombra-alta)}
.tu-item{animation:tu-der .35s var(--tu-e) backwards;transition:transform var(--tu-normal) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e)}
.tu-item:hover{transform:translateX(3px) scale(1.012);box-shadow:var(--tu-sombra-alta)}
.tu-insignia{transition:transform var(--tu-rapido) var(--tu-e)}
.tu-insignia:hover{transform:translateY(-1px) scale(1.07)}

/* Números que cuentan, anillo que se llena y barras de progreso (una sola vez, al cargar) */
.tu-num{counter-reset:tu-n var(--tu-n);animation:tu-contar .9s var(--tu-e) .1s backwards}
.tu-num::after{content:counter(tu-n);font-size:calc(1em*var(--tu-ok,0))}
.tu-num>b{font:inherit;font-size:calc(1em*(1 - var(--tu-ok,0)))}
.tu-anillo{animation:tu-llenar calc(.9s*var(--tu-ok,0)) var(--tu-e) .1s backwards}
[data-testid="stProgressBarTrack"]>div{position:relative;overflow:hidden;animation:tu-barra .8s var(--tu-e) .1s backwards}
[data-testid="stProgressBarTrack"]>div::after{content:none}

/* Botones: elevación de 1 px, sombra más marcada al pasar el mouse y «presionado» al hacer clic */
[data-testid^="stBaseButton-primary"],[data-testid^="stBaseButton-secondary"]{position:relative;overflow:hidden}
[data-testid^="stBaseButton-primary"]{transition:transform var(--tu-rapido) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e),filter var(--tu-rapido) var(--tu-e)}
[data-testid^="stBaseButton-primary"]:hover:not(:disabled){transform:translateY(-1px) scale(1.03);filter:brightness(1.06);
box-shadow:0 10px 22px -10px rgba(11,61,145,.75)}
[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]{transition:transform var(--tu-rapido) var(--tu-e),border-color var(--tu-rapido) var(--tu-e),
color var(--tu-rapido) var(--tu-e),background var(--tu-rapido) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e)}
[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]:hover:not(:disabled){transform:translateY(-1px) scale(1.03);box-shadow:0 6px 14px -8px rgba(11,61,145,.4)}
[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"]:hover:not(:disabled){transform:scale(1.03)}
[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"]{transition:transform var(--tu-rapido) var(--tu-e),background var(--tu-rapido) var(--tu-e),border-color var(--tu-rapido) var(--tu-e)}
[data-testid^="stBaseButton-primary"]:active:not(:disabled),[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]:active:not(:disabled),
[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"]:active:not(:disabled){transform:scale(.98);transition-duration:.06s}
[data-testid^="stBaseButton-primary"]::before,[data-testid^="stBaseButton-secondary"]::before{content:"";position:absolute;left:50%;top:50%;
width:140%;aspect-ratio:1;border-radius:50%;pointer-events:none;background:radial-gradient(circle,rgba(255,255,255,.35) 0%,rgba(255,255,255,0) 62%);
transform:translate(-50%,-50%) scale(1.4);opacity:0;transition:transform .4s var(--tu-e),opacity .5s var(--tu-e)}
[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]::before{background:radial-gradient(circle,rgba(31,99,201,.22) 0%,rgba(31,99,201,0) 62%)}
[data-testid^="stBaseButton-primary"]:active::before,[data-testid^="stBaseButton-secondary"]:active::before{transform:translate(-50%,-50%) scale(0);opacity:1;transition:0s}
[data-testid^="stBaseButton"]:focus-visible{outline:none;box-shadow:0 0 0 3px rgba(31,99,201,.35)}

/* Avisos: entrada corta; el error hace una sacudida leve */
[data-testid="stAlertContainer"]{animation:tu-rebote .3s var(--tu-e) backwards}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]){animation:tu-rebote .3s var(--tu-e) backwards,tu-sacudir .35s var(--tu-e) .1s}
[data-testid="stAlertDynamicIcon"]{animation:tu-pop .3s var(--tu-e) .1s backwards}

/* Campos de texto, listas y pestañas: anillo de enfoque suave */
[data-testid="stTextInputRootElement"],[data-testid="stTextAreaRootElement"],[data-testid="stNumberInputContainer"],
[data-testid="stSelectbox"] [role="group"]{transition:box-shadow var(--tu-normal) var(--tu-e),border-color var(--tu-normal) var(--tu-e)}
[data-testid="stTextInputRootElement"]:focus-within,[data-testid="stTextAreaRootElement"]:focus-within,[data-testid="stNumberInputContainer"]:focus-within,
[data-testid="stSelectbox"] [role="group"]:focus-within{box-shadow:0 0 0 3px rgba(31,99,201,.22)}
[data-testid="stTab"]{transition:color var(--tu-rapido) var(--tu-e),transform var(--tu-normal) var(--tu-e)}
[data-testid="stTab"]:hover{transform:scale(1.05)}

/* Menú lateral */
[data-testid="stSidebarNavLink"]{position:relative;animation:tu-izq .3s var(--tu-e) backwards;transition:background var(--tu-rapido) var(--tu-e),transform var(--tu-normal) var(--tu-e)}
[data-testid="stSidebarNavLink"]:hover{transform:scale(1.03);transform-origin:left center}
[data-testid="stSidebarNavLink"]::before{content:"";position:absolute;left:-2px;top:22%;bottom:22%;width:3px;border-radius:3px;
background:linear-gradient(#5B9BEF,#0EA5E9);transform:scaleY(0);transition:transform var(--tu-normal) var(--tu-e)}
[data-testid="stSidebarNavLink"][aria-current="page"]::before{transform:scaleY(1)}
[data-testid="stSidebarUserContent"] [data-testid="stElementContainer"]{animation:tu-izq .3s var(--tu-e) backwards}
.tu-usuario{transition:background var(--tu-normal) var(--tu-e),border-color var(--tu-normal) var(--tu-e),transform var(--tu-normal) var(--tu-e)}
.tu-usuario:hover{transform:scale(1.02);background:rgba(255,255,255,.1);border-color:rgba(157,187,240,.4)}
.tu-avatar{animation:none}

/* Chat: el tutor entra por la izquierda y el alumno por la derecha, con un desplazamiento mínimo */
[data-testid="stChatMessage"]{animation:tu-izq .3s var(--tu-e) backwards}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){animation-name:tu-der}
[data-testid="stChatMessageAvatarAssistant"],[data-testid="stChatMessageAvatarUser"]{animation:tu-pop .3s var(--tu-e) .1s backwards}
[data-testid="stSpinner"]{animation:tu-respirar 1.4s ease-in-out infinite}
[data-testid="stChatInput"]{transition:box-shadow var(--tu-normal) var(--tu-e)}
[data-testid="stChatInput"]:focus-within{box-shadow:0 0 0 3px rgba(31,99,201,.22),var(--tu-sombra)}

/* Píldoras de modo y opciones del examen */
[class*="st-key-modo_"] [data-testid="stRadioOption"]{transition:background var(--tu-normal) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e),transform var(--tu-rapido) var(--tu-e)}
[class*="st-key-modo_"] [data-testid="stRadioOption"]:hover{transform:scale(1.04)}
[class*="st-key-modo_"] [data-testid="stRadioOption"]:active{transform:scale(.97)}
[class*="st-key-modo_"] [data-testid="stRadioOption"][data-selected="true"]>div,[class*="st-key-quiz_"] [data-testid="stRadioOption"][data-selected="true"]>div{animation:tu-seleccion .2s var(--tu-e)}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]{animation:tu-der .3s var(--tu-e) backwards;transition:border-color var(--tu-rapido) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e),
background var(--tu-rapido) var(--tu-e),transform var(--tu-rapido) var(--tu-e)}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]:nth-of-type(2){animation-delay:.05s}[class*="st-key-quiz_"] [data-testid="stRadioOption"]:nth-of-type(3){animation-delay:.1s}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]:nth-of-type(4){animation-delay:.15s}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]:hover{transform:translateX(2px) scale(1.012);box-shadow:var(--tu-sombra)}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]:active{transform:scale(.99)}
.tu-marca{animation:tu-pop .3s var(--tu-e) .1s backwards}

/* Íconos de lo que se puede tocar: una vibración corta y leve al pasar el mouse (una sola vez por pasada) */
[data-testid^="stBaseButton"]:hover:not(:disabled) [data-testid="stIconMaterial"],
[data-testid="stSidebarNavLink"]:hover [data-testid="stIconMaterial"],
[data-testid="stTab"]:hover span[role="img"],
[class*="st-key-modo_"] [data-testid="stRadioOption"]:hover span[role="img"],
[data-testid="stExpander"] summary:hover [data-testid="stIconMaterial"],
[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) svg,
.tu-dato:hover .tu-dato-icono svg,.tu-item:hover .tu-item-icono svg,.tit:hover .tit-icono svg,
.tu-rasgo:hover .tu-rasgo-icono svg,.tu-chip:hover svg,.tu-insignia:hover svg{display:inline-block;animation:tu-vibrar .9s ease-in-out 1;transform-origin:50% 60%}
[data-testid="stTab"] span[role="img"],[class*="st-key-modo_"] [data-testid="stRadioOption"] span[role="img"]{display:inline-block}

/* Medallas y tarjetas de logros: entrada con «pop» y, al pasar el mouse, un giro corto */
.tu-med{animation:tu-pop .5s var(--tu-e) backwards;transition:transform var(--tu-normal) var(--tu-e)}
.tu-lg,.tu-vit,.tu-vitrina{animation:tu-rebote .4s var(--tu-e) backwards}
.tu-lg{transition:transform var(--tu-normal) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e)}
.tu-lg:hover{transform:translateY(-2px) scale(1.015);box-shadow:var(--tu-sombra-alta)}
.tu-lg:hover .tu-med:not(.n0),.tu-vit:hover .tu-med{transform:scale(1.1) rotate(-4deg)}
.tu-lg:hover .tu-med svg,.tu-vit:hover .tu-med svg{animation:tu-vibrar .9s ease-in-out 1}
.tu-pos.p1{animation:tu-resplandor 3.2s ease-in-out infinite}

/* Calendario y logros: entrada corta y elevación leve */
.tu-cal-tarjeta{animation:tu-rebote .4s var(--tu-e) backwards}
.tu-logro{animation:tu-rebote .4s var(--tu-e) backwards;transition:transform var(--tu-normal) var(--tu-e),box-shadow var(--tu-normal) var(--tu-e)}
.tu-logro:hover{transform:translateY(-2px) scale(1.02);box-shadow:var(--tu-sombra-alta)}
.tu-logro.logrado:hover .tu-logro-icono svg{display:inline-block;animation:tu-vibrar .9s ease-in-out 1}
.tu-cal-celda{transition:transform var(--tu-rapido) var(--tu-e)}
.tu-cal-celda:not(.futuro):hover{transform:scale(1.18)}
.tu-logro-barra i{animation:tu-barra .8s var(--tu-e) .1s backwards}

/* Confeti (se usa solo en logros importantes; no ocupa lugar en la página ni recibe la entrada) */
[data-testid="stElementContainer"]:has(.tu-confeti){position:absolute;width:0;height:0}
.tu-confeti{position:fixed;inset:0;z-index:1000001;pointer-events:none;overflow:hidden}
.tu-confeti b{position:absolute;left:50%;top:62%;animation:tu-conf-x var(--t) cubic-bezier(.1,.75,.3,1) var(--d) both}
.tu-confeti i{display:block;width:var(--w);height:var(--h);background:var(--c);border-radius:var(--br);opacity:0;animation:tu-conf-y var(--t) linear var(--d) both}

/* Inicio de sesión */
.tu-acceso-hero{animation:tu-subir .5s var(--tu-e) backwards}
.tu-acceso-logo,.tu-acceso-titulo,.tu-acceso-texto{animation:tu-subir .45s var(--tu-e) backwards}
.tu-acceso-titulo{animation-delay:.08s}.tu-acceso-texto{animation-delay:.14s}
.tu-rasgo{animation:tu-subir .4s var(--tu-e) .2s backwards;transition:background var(--tu-normal) var(--tu-e),border-color var(--tu-normal) var(--tu-e)}
.tu-rasgo:nth-child(2){animation-delay:.27s}.tu-rasgo:nth-child(3){animation-delay:.34s}
.tu-rasgo:hover{transform:none;background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.3)}
.tu-rasgo-icono{transition:background var(--tu-normal) var(--tu-e)}
.tu-rasgo:hover .tu-rasgo-icono{background:rgba(255,255,255,.26)}
.st-key-tarjeta_acceso{animation:tu-rebote .5s var(--tu-e) .1s backwards}
""".replace("%B", _BLOQUE)
    # cascada: cada elemento de la pantalla entra apenas después que el anterior (máximo 0,28 s de retraso)
    + "".join(f"{_BLOQUE}>*:nth-child({i}){{animation-delay:{(i - 1) * 0.035:.3f}s}}" for i in range(2, 9))
    + f"{_BLOQUE}>*:nth-child(n+9){{animation-delay:.28s}}"
)


def es_oscuro() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def aplicar_estilo() -> None:
    """Inserta la hoja de estilos de la app (se llama una vez por ejecución desde app.py)."""
    st.html(f"<style>{CSS}{CSS_OSCURO if es_oscuro() else ''}{CSS_ANIMACIONES if ANIMACIONES else ''}</style>")


def _ficha(token) -> str:
    """Texto seguro para usarlo dentro del nombre de una animación CSS."""
    return re.sub(r"[^a-z0-9]+", "-", str(token).lower()).strip("-") or "x"


def transicion(token) -> None:
    """Hace que las animaciones de entrada se repitan cuando cambia `token` (app.py lo llama con la página actual).

    Al navegar, Streamlit reutiliza los elementos que ya están en pantalla, y una animación CSS solo vuelve a
    correr si cambia su nombre. Por eso cada página usa los mismos fotogramas con un nombre propio.
    """
    if not ANIMACIONES:
        return
    k = _ficha(token)
    nombres = ("subir", "rebote", "pop", "izq", "der", "contar", "llenar", "barra")
    reglas = "".join(f"@keyframes tu-{n}-{k}{{{_FOTOGRAMAS[n]}}}" for n in nombres) + (
        f"{_APP} {_BLOQUE}>*:not(:has(.tu-confeti)){{animation-name:tu-subir-{k}}}"
        f"{_APP} .tu-dato,{_APP} .tu-anillo-tarjeta{{animation-name:tu-rebote-{k}}}"
        f"{_APP} .tu-item{{animation-name:tu-der-{k}}}"
        f"{_APP} .tu-hero-icono{{animation-name:tu-pop-{k},tu-flotar-y}}"
        f"{_APP} .tu-hero-titulo,{_APP} .tu-hero-sub{{animation-name:tu-izq-{k}}}"
        f"{_APP} .tu-chip{{animation-name:tu-pop-{k}}}"
        f"{_APP} .tu-num{{animation-name:tu-contar-{k}}}"
        f"{_APP} .tu-anillo{{animation-name:tu-llenar-{k}}}"
        f'{_APP} [data-testid="stMain"] [data-testid="stProgressBarTrack"]>div{{animation-name:tu-barra-{k}}}')
    st.html(f"<style>{reglas}</style>")


def reanimar(clave: str, token, efecto: str = "subir", duracion: float = 0.6) -> None:
    """Repite la entrada del contenedor creado con key=`clave` cada vez que cambia `token` (p. ej. otra pregunta)."""
    if not ANIMACIONES:
        return
    nombre = f"tu-{efecto}-{_ficha(clave)}-{_ficha(token)}"
    st.html(f"<style>@keyframes {nombre}{{{_FOTOGRAMAS[efecto]}}}"
            f"{_APP} .st-key-{clave}{{animation:{nombre} {duracion}s var(--tu-e-suave) backwards}}</style>")


def reanimar_siguientes(clave: str, token) -> None:
    """Repite la entrada de todo lo que está debajo del widget con key=`clave` cuando cambia `token` (otra pestaña)."""
    if not ANIMACIONES:
        return
    nombre = f"tu-subir-{_ficha(clave)}-{_ficha(token)}"
    st.html(f"<style>@keyframes {nombre}{{{_FOTOGRAMAS['subir']}}}"
            f"{_APP} {_BLOQUE}>.st-key-{clave}~*:not(:has(.tu-confeti)){{animation-name:{nombre}}}</style>")


def confeti(piezas: int = 80) -> None:
    """Estallido de confeti hecho solo con CSS; se dibuja en la ejecución en que se llama y dura unos 2 segundos."""
    if not ANIMACIONES:
        return
    colores = ("#0B3D91", "#1F63C9", "#5B9BEF", "#0EA5E9", "#F59E0B", "#FBBF24", "#22C55E", "#F43F5E", "#FFFFFF")
    azar = random.Random()
    trozos = []
    for _ in range(piezas):
        trozos.append(
            f'<b style="--dx:{azar.uniform(-46, 46):.1f}vw;--d:{azar.uniform(0, 0.22):.2f}s;--t:{azar.uniform(1.5, 2.5):.2f}s">'
            f'<i style="--c:{azar.choice(colores)};--up:-{azar.uniform(16, 60):.0f}vh;'
            f'--r:{azar.choice((-1, 1)) * azar.randint(380, 1100)}deg;--w:{azar.randint(7, 12)}px;'
            f'--h:{azar.randint(10, 18)}px;--br:{azar.choice(("2px", "2px", "50%"))}"></i></b>')
    _html(f'<div class="tu-confeti" aria-hidden="true">{"".join(trozos)}</div>')
