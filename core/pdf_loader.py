"""Extrae el texto de un PDF con PyPDF2 y lo convierte en Documentos de LlamaIndex."""
from llama_index.core import Document
from PyPDF2 import PdfReader


def extraer_documentos(archivo, tema_id: int, documento_id: int, nombre: str) -> list[Document]:
    """Devuelve un Document por página con texto. Lanza ValueError si el PDF no sirve."""
    reader = PdfReader(archivo)
    if reader.is_encrypted:
        raise ValueError("El PDF está protegido con contraseña.")

    docs = []
    for num, pagina in enumerate(reader.pages, start=1):
        texto = (pagina.extract_text() or "").strip()
        if not texto:
            continue
        meta = {"tema_id": tema_id, "documento_id": documento_id, "archivo": nombre, "pagina": num}
        docs.append(Document(
            text=texto,
            metadata=meta,
            # Los metadatos no se mezclan con el texto que se convierte en embedding:
            excluded_embed_metadata_keys=list(meta),
            excluded_llm_metadata_keys=list(meta),
        ))

    if not docs:
        raise ValueError("No se encontró texto. Si el PDF es un escaneo (imágenes), PyPDF2 no puede leerlo.")
    return docs
