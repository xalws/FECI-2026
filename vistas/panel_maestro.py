import streamlit as st
from sqlalchemy import select

from core import material, pdf_loader, rag, reticula
from core.auth import require_login
from core.db import get_session
from core.ui import selector_cascada
from models.schema import Asignacion, Documento

user = require_login(["maestro", "admin"])

# Iconos SVG 
SVG = {
    "book": '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
}


def titulo(icono: str, texto: str, nivel: int = 3):
    """Encabezado con icono SVG en línea."""
    size = 30 if nivel == 1 else 22
    st.markdown(
        f'<div class="tit"><svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{SVG[icono]}</svg><h{nivel}>{texto}</h{nivel}></div>',
        unsafe_allow_html=True,
    )


# Estilo
st.markdown(
    """
    <style>
    /* Encabezados con icono SVG */
    .tit { display: flex; align-items: center; gap: .6rem; margin: .6rem 0 .4rem; }
    .tit h1, .tit h2, .tit h3 { margin: 0; padding: 0; }
    .tit svg { flex-shrink: 0; }

    /* Tarjetas de métricas */
    div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 12px;
        padding: 14px 18px;
    }

    /* Botones redondeados */
    .stButton > button, .stFormSubmitButton > button { border-radius: 10px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

titulo("book", "Material de entrenamiento", nivel=1)

# Maestro
if user["rol"] == "admin":
    permitidas = None
else:
    with get_session() as s:
        permitidas = list(s.scalars(select(Asignacion.materia_id).where(Asignacion.maestro_id == user["id"])))
    if not permitidas:
        st.info("El administrador todavía no te ha asignado materias.")
        st.stop()

with st.sidebar:
    st.divider()
    titulo("book", "Elige el tema")
    sel = selector_cascada(hasta="tema", materias_permitidas=permitidas, prefix="maestro")
tema_id = sel.get("tema")
materia_id = sel.get("materia")
if materia_id is None:
    st.info("Elige la materia en el menú de la izquierda.")
    st.stop()

with st.container(border=True):
    modo = st.radio("¿Dónde quieres subir el material?",
                    ["Toda la materia (se reparte por los temas de la retícula)", "Un tema específico"],
                    horizontal=True)

if modo.startswith("Toda"):
    temas_materia = reticula.temas_de_materia(materia_id)
    titulo("upload", "Subir material de toda la materia")
    if not temas_materia:
        st.info("Esta materia todavía no tiene temas. Primero sube su programa en la página «Retícula».")
        st.stop()
    st.caption(f"La app asigna cada fragmento del PDF al tema de la retícula que mejor lo describe "
               f"({len(temas_materia)} temas). Lo que no se parezca a ningún tema no se guarda.")

    # Cobertura
    cob = material.cobertura(materia_id)
    con_material = sum(1 for c in cob if c["estado"] == "ok")
    sin_material = sum(1 for c in cob if c["estado"] == "sin_material")
    pdfs = sorted({d["archivo"] for c in cob for d in c["documentos"]})

    titulo("chart", "Cobertura de la materia")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(":material/list: Temas", len(cob))
    m2.metric(":material/check_circle: Con material", con_material)
    m3.metric(":material/error: Sin material", sin_material)
    m4.metric(":material/picture_as_pdf: PDFs", len(pdfs))
    st.progress(con_material / len(cob), text=f"{con_material} de {len(cob)} temas con material")

    ESTADOS = {"ok": "Con material", "sin_material": "Sin material",
               "sin_indice": "Documento sin contenido indexado"}
    st.dataframe([{"Unidad": c["unidad"], "Tema": c["tema"], "Estado": ESTADOS[c["estado"]],
                   "Fragmentos": c["fragmentos"],
                   "PDFs": ", ".join(sorted({d["archivo"] for d in c["documentos"]}))} for c in cob],
                 hide_index=True)
    if any(c["estado"] == "sin_indice" for c in cob):
        st.warning("Hay temas con un PDF registrado cuyo contenido no está en la base de datos (se subió cuando el "
                   "índice todavía era local). Para recuperarlo, quien lo subió debe ejecutar "
                   "`python scripts/migrar_chroma_a_bd.py` en su computadora, o volver a subir el PDF.",
                   icon=":material/warning:")
    if pdfs:
        with st.expander(f"PDFs de esta materia ({len(pdfs)})"):
            for nombre in pdfs:
                a, b = st.columns([5, 1])
                a.write(nombre)
                if b.button("Eliminar", key=f"del_pdf_{nombre}", icon=":material/delete:"):
                    material.eliminar_archivo(materia_id, nombre)
                    st.rerun()

    titulo("upload", "Subir material")
    with st.container(border=True):
        archivos_m = st.file_uploader("Elige uno o más PDFs (con texto, no escaneados)", type="pdf",
                                      accept_multiple_files=True, key="pdf_materia")
        if archivos_m and st.button("Procesar y repartir por temas", type="primary", icon=":material/upload:"):
            for f in archivos_m:
                if material.ya_subido(materia_id, f.name):
                    st.warning(f"«{f.name}» ya está en esta materia, elimínalo primero si quieres reemplazarlo.")
                    continue
                try:
                    with st.spinner(f"Procesando {f.name}…"):
                        r = material.subir_a_materia(f, f.name, materia_id, user["id"])
                    if r["por_tema"]:
                        st.success(f"{f.name}: material repartido en {len(r['por_tema'])} tema(s).",
                                   icon=":material/check_circle:")
                        st.dataframe([{"tema": t, "fragmentos": n} for t, n in r["por_tema"].items()],
                                     hide_index=True)
                    else:
                        st.warning(f"{f.name}: ningún fragmento se parece a los temas de la retícula.")
                    if r["sin_tema"]:
                        st.caption(f"{r['sin_tema']} fragmento(s) no se parecían a ningún tema y no se guardaron.")
                except Exception as e:
                    st.error(f"{f.name}: {e}", icon=":material/error:")
    st.stop()

if tema_id is None:
    st.info("Elige el tema en el menú de la izquierda.")
    st.stop()

st.divider()
titulo("file", "Documentos de este tema")
with get_session() as s:
    docs = s.scalars(select(Documento).where(Documento.tema_id == tema_id).order_by(Documento.id.desc())).all()
if not docs:
    st.caption("Aún no hay PDFs.")
filtro = st.text_input("Buscar documento", key="buscar_doc", icon=":material/search:").strip().lower() if docs else ""
visibles = [d for d in docs if filtro in d.nombre_archivo.lower()]
if docs and not visibles:
    st.caption("Ningún documento coincide.")
for d in visibles:
    with st.container(border=True):
        a, b = st.columns([5, 1], vertical_alignment="center")
        a.write(f"**{d.nombre_archivo}** — {d.num_chunks} fragmentos — {d.fecha:%d/%m/%Y %H:%M}")
        if b.button("Eliminar", key=f"del_{d.id}", icon=":material/delete:"):
            rag.eliminar_documento(tema_id, d.id)
            with get_session() as s:
                s.delete(s.get(Documento, d.id))
            st.rerun()

titulo("upload", "Subir nuevos PDFs")
with st.container(border=True):
    archivos = st.file_uploader("Elige uno o más PDFs (con texto, no escaneados)", type="pdf",
                                accept_multiple_files=True)
    if archivos and st.button("Procesar y entrenar", type="primary", icon=":material/model_training:"):
        nombres_existentes = {d.nombre_archivo for d in docs}
        for f in archivos:
            if f.name in nombres_existentes:
                st.warning(f"«{f.name}» ya existe en este tema, elimínalo primero si quieres reemplazarlo.")
                continue
            doc_id = None
            try:
                with st.spinner(f"Procesando {f.name}…"):
                    with get_session() as s:
                        doc = Documento(tema_id=tema_id, maestro_id=user["id"], nombre_archivo=f.name, num_chunks=0)
                        s.add(doc)
                        s.flush()
                        doc_id = doc.id
                        paginas = pdf_loader.extraer_documentos(f, tema_id, doc_id, f.name)
                        doc.num_chunks = rag.indexar(tema_id, paginas)
                st.success(f"{f.name}: {doc.num_chunks} fragmentos indexados.", icon=":material/check_circle:")
            except Exception as e:
                if doc_id:
                    rag.eliminar_documento(tema_id, doc_id)  # limpia lo que haya quedado en Chroma
                st.error(f"{f.name}: {e}", icon=":material/error:")