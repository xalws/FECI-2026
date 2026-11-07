import streamlit as st
from sqlalchemy import select

from core import pdf_loader, rag
from core.auth import require_login
from core.db import get_session
from core.ui import selector_cascada
from models.schema import Asignacion, Documento

user = require_login(["maestro", "admin"])

st.title("Material de entrenamiento")

# Maestro: solo sus materias. Admin: todas.
if user["rol"] == "admin":
    permitidas = None
else:
    with get_session() as s:
        permitidas = list(s.scalars(select(Asignacion.materia_id).where(Asignacion.maestro_id == user["id"])))
    if not permitidas:
        st.info("El administrador todavía no te ha asignado materias.")
        st.stop()

sel = selector_cascada(hasta="tema", materias_permitidas=permitidas, prefix="maestro")
tema_id = sel.get("tema")
if tema_id is None:
    st.stop()

st.divider()
st.subheader("Documentos de este tema")
with get_session() as s:
    docs = s.scalars(select(Documento).where(Documento.tema_id == tema_id).order_by(Documento.id.desc())).all()
if not docs:
    st.caption("Aún no hay PDFs. La IA no responderá nada en este tema hasta que subas material.")
filtro = st.text_input("Buscar documento", key="buscar_doc").strip().lower() if docs else ""
visibles = [d for d in docs if filtro in d.nombre_archivo.lower()]
if docs and not visibles:
    st.caption("Ningún documento coincide.")
for d in visibles:
    a, b = st.columns([5, 1])
    a.write(f"**{d.nombre_archivo}** — {d.num_chunks} fragmentos — {d.fecha:%d/%m/%Y %H:%M}")
    if b.button("Eliminar", key=f"del_{d.id}"):
        rag.eliminar_documento(tema_id, d.id)
        with get_session() as s:
            s.delete(s.get(Documento, d.id))
        st.rerun()

st.subheader("Subir nuevos PDFs")
archivos = st.file_uploader("Elige uno o más PDFs (con texto, no escaneados)", type="pdf",
                            accept_multiple_files=True)
if archivos and st.button("Procesar y entrenar", type="primary"):
    nombres_existentes = {d.nombre_archivo for d in docs}
    for f in archivos:
        if f.name in nombres_existentes:
            st.warning(f"«{f.name}» ya existe en este tema; elimínalo primero si quieres reemplazarlo.")
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
            st.success(f"✅ {f.name}: {doc.num_chunks} fragmentos indexados.")
        except Exception as e:
            if doc_id:
                rag.eliminar_documento(tema_id, doc_id)  
            st.error(f"❌ {f.name}: {e}")
