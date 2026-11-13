import random

import chromadb
import numpy as np
import streamlit as st
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from core.config import CHROMA_PATH, EMBED_MODEL, MIN_SCORE, TOP_K, UMBRAL_TEMA


@st.cache_resource(show_spinner="Cargando modelo (la primera vez descarga ~200 MB)...")
def _embed_model():
    return FastEmbedEmbedding(model_name=EMBED_MODEL)


@st.cache_resource
def _client():
    return chromadb.PersistentClient(path=CHROMA_PATH)


def _coleccion(tema_id: int):
    return _client().get_or_create_collection(f"tema_{tema_id}", metadata={"hnsw:space": "cosine"})


def partir(documentos: list[Document]) -> list:
    return SentenceSplitter(chunk_size=800, chunk_overlap=100).get_nodes_from_documents(documentos)


def indexar_nodos(tema_id: int, nodos: list) -> int:
    vector_store = ChromaVectorStore(chroma_collection=_coleccion(tema_id))
    storage = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodos, storage_context=storage, embed_model=_embed_model())
    return len(nodos)


def indexar(tema_id: int, documentos: list[Document]) -> int:
    return indexar_nodos(tema_id, partir(documentos))


def clasificar_por_similitud(vec_nodos: list, vec_temas: list, umbral: float) -> list[int | None]:
    # Para cada fragmento devuelve la posición del tema más parecido (similitud coseno), o None si ninguno
    # llega al umbral.
    a = np.asarray(vec_nodos, dtype=float)
    b = np.asarray(vec_temas, dtype=float)
    a /= np.linalg.norm(a, axis=1, keepdims=True) + 1e-12
    b /= np.linalg.norm(b, axis=1, keepdims=True) + 1e-12
    sim = a @ b.T
    mejor, valor = sim.argmax(axis=1), sim.max(axis=1)
    return [int(m) if v >= umbral else None for m, v in zip(mejor, valor)]


def repartir_por_temas(nodos: list, temas: list[dict]) -> tuple[dict[int, list], int]:
    # Asigna cada fragmento al tema de la retícula que mejor lo describe.
    # Devuelve ({tema_id: [fragmentos]}, cantidad de fragmentos sin tema claro).
    if not nodos or not temas:
        return {}, len(nodos)
    modelo = _embed_model()
    vec_nodos = modelo.get_text_embedding_batch([n.get_content(metadata_mode=MetadataMode.NONE) for n in nodos])
    vec_temas = modelo.get_text_embedding_batch([t["descripcion"] for t in temas])
    por_tema: dict[int, list] = {}
    sin_tema = 0
    for nodo, k in zip(nodos, clasificar_por_similitud(vec_nodos, vec_temas, UMBRAL_TEMA)):
        if k is None:
            sin_tema += 1
        else:
            por_tema.setdefault(temas[k]["id"], []).append(nodo)
    return por_tema, sin_tema


def buscar(tema_id: int, consulta: str) -> list[dict]:
    col = _coleccion(tema_id)
    if col.count() == 0:
        return []
    vector = _embed_model().get_query_embedding(consulta)
    res = col.query(query_embeddings=[vector], n_results=min(TOP_K, col.count()),
                    include=["documents", "metadatas", "distances"])
    fragmentos = []
    for texto, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        score = 1 - dist
        if score >= MIN_SCORE:
            fragmentos.append({"texto": texto, "score": score,
                               "archivo": meta.get("archivo", ""), "pagina": meta.get("pagina", "")})
    return fragmentos


def chunks_aleatorios(tema_id: int, n: int = 3) -> list[dict]:
    col = _coleccion(tema_id)
    if col.count() == 0:
        return []
    textos = col.get(include=["documents"])["documents"]
    return [{"texto": t, "score": 1.0, "archivo": "", "pagina": ""}
            for t in random.sample(textos, min(n, len(textos)))]


def eliminar_documento(tema_id: int, documento_id: int) -> None:
    _coleccion(tema_id).delete(where={"documento_id": documento_id})


def total_chunks(tema_id: int) -> int:
    return _coleccion(tema_id).count()
