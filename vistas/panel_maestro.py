import streamlit as st
from sqlalchemy import select

from core import material, pdf_loader, rag, reticula, stats
from core.auth import require_login
from core.db import get_session
from core.estilo import datos, encabezado, fecha_local, lista, titulo
from core.ui import selector_cascada
from models.schema import Asignacion, Documento

user = require_login(["maestro", "admin"])

# Los íconos, títulos y estilos vienen de core/estilo.py (compartidos por todas las pantallas)

encabezado("Material de entrenamiento", "Sube los PDFs con los que el tutor responde a tus alumnos y revisa qué temas "
           "ya tienen material.", "upload")

# El maestro ve todas las universidades, carreras y materias, pero solo puede subir material a las que tiene asignadas
if user["rol"] == "admin":
    permitidas = None
else:
    with get_session() as s:
        permitidas = set(s.scalars(select(Asignacion.materia_id).where(Asignacion.maestro_id == user["id"])))

with st.sidebar:
    st.divider()
    titulo("book", "Elige el tema")
    sel = selector_cascada(hasta="tema", prefix="maestro")
tema_id = sel.get("tema")
materia_id = sel.get("materia")
if materia_id is None:
    st.info("Elige la materia en el menú de la izquierda.")
    st.stop()
if permitidas is not None and materia_id not in permitidas:
    st.warning("Esta materia no está asignada a ti, así que no puedes subirle material. Pídele al administrador que "
               "te la asigne (o elige otra en el menú de la izquierda)."
               + ("" if permitidas else " Todavía no tienes ninguna materia asignada."), icon=":material/lock:")
    st.stop()

# Temas de esta materia donde varios alumnos preguntaron algo que el material no cubre
try:
    faltantes = stats.material_faltante(stats.preguntas_sin_respuesta([materia_id]))
except Exception:  # un fallo de las estadísticas no debe impedir subir material
    faltantes = None
if faltantes is not None and not faltantes.empty:
    titulo("bulb", f"Tus alumnos piden material en {len(faltantes)} {'tema' if len(faltantes) == 1 else 'temas'}")
    lista([{"icono": "help", "titulo": f["tema"], "sub": f"{f['alumnos']} alumnos distintos preguntaron", "tono": "ambar",
            "texto": f"Por ejemplo: «{f['ejemplo'][:140]}»"} for _, f in faltantes.head(5).iterrows()])

st.caption("¿Dónde quieres subir el material?")
modo = st.radio("¿Dónde quieres subir el material?",
                [":material/account_tree: Toda la materia (se reparte por los temas de la retícula)",
                 ":material/topic: Un tema específico"],
                horizontal=True, label_visibility="collapsed", key="modo_material")

if "Toda la materia" in modo:
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
    datos([{"icono": "layers", "etiqueta": "Temas", "valor": len(cob), "detalle": "en la retícula", "tono": "indigo"},
           {"icono": "check", "etiqueta": "Con material", "valor": con_material, "detalle": "listos para el tutor",
            "tono": "verde"},
           {"icono": "x", "etiqueta": "Sin material", "valor": sin_material, "detalle": "conviene subir PDFs",
            "tono": "ambar"},
           {"icono": "file", "etiqueta": "PDFs", "valor": len(pdfs), "detalle": "en esta materia", "tono": "violeta"}])
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
        a.write(f"**{d.nombre_archivo}** — {d.num_chunks} fragmentos — {fecha_local(d.fecha):%d/%m/%Y %H:%M}")
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