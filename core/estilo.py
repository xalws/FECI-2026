"""Identidad visual de la aplicación: paleta, íconos, hoja de estilos y componentes de presentación.

Toda la apariencia vive aquí y en .streamlit/config.toml (colores y tipografía del tema). Las pantallas solo
llaman a estas funciones (encabezado, titulo, datos, anillo, lista...) y no repiten CSS.
Todo texto que viene del usuario o de la base de datos se escapa antes de insertarlo en HTML.
"""
import html
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st

ZONA_POR_DEFECTO = "America/Ciudad_Juarez"

# (color del ícono/acento, fondo suave)
TONOS = {
    "indigo": ("#4F46E5", "#EEF2FF"),
    "violeta": ("#7C3AED", "#F5F3FF"),
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


TONOS_OSCURO = {"indigo": "#818CF8", "violeta": "#A78BFA", "cielo": "#38BDF8", "verde": "#34D399", "ambar": "#FBBF24",
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
    _html(f'<div class="tu-hero{" tu-hero-compacto" if compacto else ""}"><div class="tu-hero-fila">'
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
            f'<div class="tu-dato" style="--color:{color};--fondo:{fondo};animation-delay:{i * 0.06:.2f}s">'
            f'<div class="tu-dato-cab"><span class="tu-dato-icono">{svg(d.get("icono", "circle"), 19)}</span>'
            f'<span class="tu-dato-etiqueta">{_e(d["etiqueta"])}</span></div>'
            f'<div class="tu-dato-valor">{_e(d["valor"])}</div>{detalle}</div>')
    _html(f'<div class="tu-datos">{"".join(tarjetas)}</div>')


def insignia(texto: str, tono: str = "indigo", icono: str | None = None) -> str:
    color, fondo = _tono(tono)
    return (f'<span class="tu-insignia" style="--color:{color};--fondo:{fondo}">'
            f'{svg(icono, 13) if icono else ""}{_e(texto)}</span>')


def anillo(porcentaje: float, titulo: str, detalle: str = "", etiqueta: str = "", tono: str = "indigo") -> None:
    """Tarjeta con un anillo de avance (0 a 100) y su explicación."""
    p = max(0, min(100, round(porcentaje)))
    extra = insignia(etiqueta, tono, "award") if etiqueta else ""
    _html(f'<div class="tu-anillo-tarjeta"><div class="tu-anillo" style="--p:{p}">'
          f'<div class="tu-anillo-centro">{p}%<small>avance</small></div></div>'
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
                           stops=[alt.GradientStop(color="rgba(79,70,229,0.02)", offset=0),
                                  alt.GradientStop(color="rgba(79,70,229,0.32)", offset=1)])
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
    st.sidebar.markdown(
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
:root{--tu-indigo:#4F46E5;--tu-violeta:#7C3AED;--tu-cielo:#0EA5E9;--tu-tinta:#1E1B4B;--tu-gris:#64748B;
--tu-borde:#E2E5F1;--tu-suave:#EEF2FF;--tu-degradado:linear-gradient(135deg,#4F46E5 0%,#7C3AED 100%);
--tu-sombra:0 1px 2px rgba(30,27,75,.05),0 6px 20px rgba(30,27,75,.06);
--tu-sombra-alta:0 2px 6px rgba(30,27,75,.07),0 16px 34px rgba(30,27,75,.11);
--tu-texto:#334155;--tu-sup:#fff;--tu-pista:#E7E9F5;--tu-burbuja:linear-gradient(135deg,#EEF2FF,#F5F3FF);}
[style*="--fondo"]{--fondo:color-mix(in srgb,var(--color) 13%,transparent)!important}
@keyframes tu-aparecer{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@keyframes tu-degradado{0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%}}
@keyframes tu-flotar{0%,100%{transform:translate(0,0)}50%{transform:translate(-10px,12px)}}
@keyframes tu-latido{0%,100%{box-shadow:0 0 0 0 rgba(79,70,229,.35)}50%{box-shadow:0 0 0 8px rgba(79,70,229,0)}}

/* Lienzo general */
[data-testid="stMainBlockContainer"]{max-width:1180px;padding-top:3.6rem;padding-bottom:4rem}
[data-testid="stHeader"]{background:rgba(246,247,251,.78);backdrop-filter:blur(10px)}
[data-testid="stAppDeployButton"]{display:none}
hr{border-color:var(--tu-borde)!important}
[data-testid="stSidebar"] hr{border-color:rgba(165,180,252,.16)!important;margin:1.1rem 0!important}

/* Encabezado principal */
.tu-hero{position:relative;overflow:hidden;border-radius:22px;padding:26px 30px;margin:0 0 1.3rem;color:#fff;
background:linear-gradient(120deg,#312E81 0%,#4F46E5 38%,#7C3AED 70%,#0EA5E9 120%);background-size:220% 220%;
animation:tu-degradado 16s ease infinite,tu-aparecer .5s ease-out both;
box-shadow:0 20px 44px -22px rgba(79,70,229,.65)}
.tu-hero::before{content:"";position:absolute;width:260px;height:260px;right:-70px;top:-90px;border-radius:50%;
background:radial-gradient(circle,rgba(255,255,255,.28),rgba(255,255,255,0) 70%);animation:tu-flotar 9s ease-in-out infinite}
.tu-hero::after{content:"";position:absolute;width:180px;height:180px;right:22%;bottom:-120px;border-radius:50%;
background:radial-gradient(circle,rgba(14,165,233,.35),rgba(14,165,233,0) 70%);animation:tu-flotar 12s ease-in-out infinite reverse}
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
[data-testid="stSidebar"] .tit h1,[data-testid="stSidebar"] .tit h2,[data-testid="stSidebar"] .tit h3,[data-testid="stSidebar"] .tit h4{color:#EEF2FF}
[data-testid="stSidebar"] .tit-icono{background:rgba(165,180,252,.14);color:#A5B4FC}

/* Tarjetas de datos */
.tu-datos{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));gap:14px;margin:.2rem 0 1.2rem}
.tu-dato{background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:16px 18px;box-shadow:var(--tu-sombra);
transition:transform .18s ease,box-shadow .18s ease;animation:tu-aparecer .45s ease-out both}
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
padding:18px 22px;margin:.3rem 0 1rem;box-shadow:var(--tu-sombra);animation:tu-aparecer .45s ease-out both}
.tu-anillo{width:104px;height:104px;flex-shrink:0;border-radius:50%;display:flex;align-items:center;justify-content:center;
background:conic-gradient(#4F46E5 0%,#7C3AED calc(var(--p)*1%),var(--tu-pista) calc(var(--p)*1%))}
.tu-anillo-centro{width:80px;height:80px;border-radius:50%;background:var(--tu-sup);display:flex;flex-direction:column;align-items:center;
justify-content:center;font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:1.35rem;color:var(--tu-tinta)}
.tu-anillo-centro small{font-family:Inter,sans-serif;font-size:.62rem;font-weight:700;color:var(--tu-gris);text-transform:uppercase;letter-spacing:.08em}
.tu-anillo-titulo{font-family:"Plus Jakarta Sans",sans-serif;font-size:1.15rem;font-weight:800;color:var(--tu-tinta);margin-bottom:6px}
.tu-anillo-detalle{margin-top:8px;font-size:.88rem;color:var(--tu-gris)}

/* Lista de tarjetas con acento */
.tu-lista{display:grid;gap:10px;margin:.3rem 0 1.1rem}
.tu-item{display:flex;gap:14px;align-items:flex-start;background:var(--tu-sup);border:1px solid var(--tu-borde);border-left:4px solid var(--color);
border-radius:14px;padding:13px 16px;box-shadow:var(--tu-sombra);transition:transform .18s ease,box-shadow .18s ease;
animation:tu-aparecer .45s ease-out both}
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
box-shadow:0 1px 2px rgba(30,27,75,.04)}
[data-testid="stMainBlockContainer"] [data-testid="stExpander"] summary:hover{color:var(--tu-indigo)}
[data-testid="stAlert"]>div{border-radius:14px}

/* Botones */
[data-testid^="stBaseButton-primary"]{background:var(--tu-degradado)!important;border:0!important;color:#fff!important;
box-shadow:0 8px 18px -8px rgba(79,70,229,.65);transition:transform .15s ease,box-shadow .15s ease,filter .15s ease}
[data-testid^="stBaseButton-primary"]:hover{transform:translateY(-1px);filter:brightness(1.07);box-shadow:0 12px 24px -10px rgba(79,70,229,.75)}
[data-testid^="stBaseButton-primary"]:active{transform:translateY(0)}
[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]{background:var(--tu-sup);border:1px solid var(--tu-borde);
color:var(--tu-tinta);transition:transform .15s ease,border-color .15s ease,color .15s ease,background .15s ease}
[data-testid="stMainBlockContainer"] [data-testid^="stBaseButton-secondary"]:hover{border-color:var(--tu-indigo);color:var(--tu-indigo);
background:#F8F9FF;transform:translateY(-1px)}
[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"]{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.16);color:#E0E7FF}
[data-testid="stSidebar"] [data-testid^="stBaseButton-secondary"]:hover{background:rgba(255,255,255,.12);border-color:#A5B4FC;color:#fff}

/* Pestañas */
[data-baseweb="tab-list"]{gap:.3rem}
[data-baseweb="tab"]{border-radius:10px 10px 0 0;padding:.55rem 1rem;font-weight:600}
[data-baseweb="tab"][aria-selected="true"]{color:var(--tu-indigo)}
[data-baseweb="tab-highlight"]{background:var(--tu-degradado)!important;height:3px;border-radius:3px}

/* Barras de progreso */
[data-testid="stProgressBarTrack"]{background:var(--tu-pista);border-radius:999px;overflow:hidden}
[data-testid="stProgressBarTrack"]>div{background:linear-gradient(90deg,#4F46E5,#7C3AED 60%,#0EA5E9)!important;border-radius:999px;
transition:transform .9s cubic-bezier(.2,.8,.2,1)}
[data-testid="stSidebar"] [data-testid="stProgressBarTrack"]{background:rgba(255,255,255,.12)}

/* Chat */
[data-testid="stChatMessage"]{background:var(--tu-sup);border:1px solid var(--tu-borde);border-radius:18px;padding:.95rem 1.15rem;
box-shadow:0 1px 2px rgba(30,27,75,.05);animation:tu-aparecer .35s ease-out both}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){background:var(--tu-burbuja);
border-color:#C7D2FE;margin-left:min(12%,6rem)}
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
[class*="st-key-modo_"] [data-testid="stRadioOption"][data-selected="true"]{background:var(--tu-degradado);box-shadow:0 8px 18px -8px rgba(79,70,229,.6)}
[class*="st-key-modo_"] [data-testid="stRadioOption"][data-selected="true"] p,[class*="st-key-modo_"] [data-testid="stRadioOption"][data-selected="true"] span{color:#fff!important}

/* Opciones del examen como tarjetas seleccionables */
[class*="st-key-quiz_"] [data-testid="stRadioGroup"]{gap:.6rem;width:100%}
[class*="st-key-quiz_"] [data-testid="stRadioGroup"]>div{width:100%}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]{width:100%;margin:0!important;background:var(--tu-sup);border:1.5px solid var(--tu-borde);
border-radius:14px;padding:.85rem 1rem;cursor:pointer;transition:border-color .15s ease,box-shadow .15s ease,transform .15s ease,background .15s ease}
[class*="st-key-quiz_"] [data-testid="stRadioOption"]:hover{border-color:#A5B4FC;transform:translateY(-1px);box-shadow:var(--tu-sombra)}
[class*="st-key-quiz_"] [data-testid="stRadioOption"][data-selected="true"]{border-color:var(--tu-indigo);background:#F5F6FF;
box-shadow:0 0 0 4px rgba(79,70,229,.12)}
[class*="st-key-quiz_"] [data-testid="stRadioOption"] p{font-size:1.02rem}

/* Menú lateral */
[data-testid="stSidebarNavLink"]{border-radius:10px;margin:2px 0;transition:background .15s ease}
[data-testid="stSidebarNavLink"]:hover{background:rgba(255,255,255,.07)}
[data-testid="stSidebarNavLink"][aria-current="page"]{background:linear-gradient(90deg,rgba(99,102,241,.38),rgba(124,58,237,.16))!important}
[data-testid="stSidebarNavLink"][aria-current="page"] p,[data-testid="stSidebarNavLink"][aria-current="page"] span{color:#fff!important;font-weight:700}
[data-testid="stNavSectionHeader"]{text-transform:uppercase;letter-spacing:.09em;font-size:.7rem!important;font-weight:700!important;color:#8E95D9!important}
.tu-usuario{display:flex;align-items:center;gap:12px;padding:12px;border-radius:16px;background:rgba(255,255,255,.06);
border:1px solid rgba(255,255,255,.1);margin:.2rem 0 .4rem}
.tu-avatar{width:42px;height:42px;flex-shrink:0;border-radius:13px;display:flex;align-items:center;justify-content:center;
background:linear-gradient(135deg,#6366F1,#A855F7);color:#fff;font-weight:800;font-size:.95rem;animation:tu-latido 3s ease-in-out infinite}
.tu-usuario-nombre{color:#fff;font-weight:700;font-size:.95rem;line-height:1.25}
.tu-rol{display:inline-block;margin-top:3px;padding:1px 9px;border-radius:999px;font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.07em}
.tu-rol-alumno{background:rgba(14,165,233,.2);color:#7DD3FC}.tu-rol-maestro{background:rgba(16,185,129,.2);color:#6EE7B7}
.tu-rol-admin{background:rgba(245,158,11,.2);color:#FCD34D}

/* Pantalla de inicio de sesión */
.tu-acceso-hero{position:relative;overflow:hidden;border-radius:26px;padding:38px 36px;color:#fff;min-height:520px;
background:linear-gradient(135deg,#1E1B4B 0%,#4338CA 45%,#7C3AED 80%,#0EA5E9 130%);background-size:200% 200%;
animation:tu-degradado 18s ease infinite,tu-aparecer .6s ease-out both;box-shadow:0 30px 60px -30px rgba(67,56,202,.75)}
.tu-acceso-hero::before{content:"";position:absolute;width:340px;height:340px;right:-120px;top:-120px;border-radius:50%;
background:radial-gradient(circle,rgba(255,255,255,.22),rgba(255,255,255,0) 70%);animation:tu-flotar 10s ease-in-out infinite}
.tu-acceso-hero::after{content:"";position:absolute;width:260px;height:260px;left:-90px;bottom:-110px;border-radius:50%;
background:radial-gradient(circle,rgba(14,165,233,.4),rgba(14,165,233,0) 70%);animation:tu-flotar 13s ease-in-out infinite reverse}
.tu-acceso-hero>*{position:relative;z-index:1}
.tu-acceso-marca{display:flex;align-items:center;gap:14px}
.tu-acceso-logo{width:56px;height:56px;border-radius:17px;display:flex;align-items:center;justify-content:center;
background:linear-gradient(135deg,#6366F1,#A855F7);box-shadow:0 10px 24px -10px rgba(0,0,0,.5);color:#fff}
.tu-acceso-nombre{font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:1.3rem;color:#fff}
.tu-acceso-lema{font-size:.86rem;color:rgba(255,255,255,.75)}
.tu-acceso-titulo{margin-top:38px;font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:2.25rem;line-height:1.12;
letter-spacing:-.02em;color:#fff}
.tu-acceso-texto{margin-top:12px;font-size:1.02rem;color:rgba(255,255,255,.85);max-width:30rem}
.tu-rasgos{display:grid;gap:12px;margin-top:30px}
.tu-rasgo{display:flex;gap:13px;align-items:flex-start;padding:13px 14px;border-radius:16px;background:rgba(255,255,255,.09);
border:1px solid rgba(255,255,255,.14);backdrop-filter:blur(6px);transition:transform .2s ease,background .2s ease;animation:tu-aparecer .6s ease-out both}
.tu-rasgo:nth-child(2){animation-delay:.12s}.tu-rasgo:nth-child(3){animation-delay:.24s}
.tu-rasgo:hover{transform:translateX(4px);background:rgba(255,255,255,.14)}
.tu-rasgo b{display:block;color:#fff;font-size:.95rem}
.tu-rasgo div span{display:block;color:rgba(255,255,255,.78);font-size:.84rem;margin-top:2px}
.tu-rasgo-icono{width:42px;height:42px;flex-shrink:0;border-radius:13px;display:inline-flex;align-items:center;justify-content:center;align-self:center;
background:rgba(255,255,255,.16);color:#fff}
.st-key-tarjeta_acceso{padding:1.7rem 1.7rem 1.3rem!important;border-radius:26px!important;box-shadow:0 24px 50px -28px rgba(30,27,75,.35)!important}
.tu-acceso-bienvenida{font-family:"Plus Jakarta Sans",sans-serif;font-weight:800;font-size:1.6rem;color:var(--tu-tinta);margin:.2rem 0 .1rem}
.tu-acceso-ayuda{color:var(--tu-gris);font-size:.92rem;margin-bottom:.4rem}

/* Pantallas angostas y movimiento reducido */
@media (max-width:760px){.tu-hero{padding:20px}.tu-hero-titulo{font-size:1.45rem}.tu-anillo-tarjeta{flex-direction:column;align-items:flex-start}
.tu-datos{gap:10px}.tu-dato{padding:14px}.tu-dato-valor{font-size:1.45rem}
.tu-acceso-hero{min-height:auto;padding:28px 24px}.tu-acceso-titulo{font-size:1.7rem;margin-top:26px}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){margin-left:0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""


CSS_OSCURO = """
:root{--tu-tinta:#E8EAFF;--tu-gris:#A3A9CF;--tu-borde:#2E2B63;--tu-suave:#25225A;--tu-pista:#2E2B63;
--tu-sombra:0 1px 2px rgba(0,0,0,.35),0 6px 20px rgba(0,0,0,.28);--tu-sombra-alta:0 2px 6px rgba(0,0,0,.4),0 16px 34px rgba(0,0,0,.4);
--tu-texto:#C7CCEE;--tu-sup:#1D1A44;--tu-burbuja:linear-gradient(135deg,#2A2766,#34286E)}
[data-testid="stHeader"]{background:rgba(17,16,40,.72)!important}
"""


def es_oscuro() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def aplicar_estilo() -> None:
    """Inserta la hoja de estilos de la app (se llama una vez por ejecución desde app.py)."""
    st.html(f"<style>{CSS}{CSS_OSCURO if es_oscuro() else ''}</style>")
