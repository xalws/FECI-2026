"""RAG: LlamaIndex (chunks + embeddings) + ChromaDB (una colección por tema)."""
import random

import chromadb
import streamlit as st
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore

from core.config import CHROMA_PATH, EMBED_MODEL, MIN_SCORE, TOP_K


@st.cache_resource(show_spinner="Cargando modelo de embeddings (la primera vez descarga ~200 MB)...")
def _embed_model():
    return FastEmbedEmbedding(model_name=EMBED_MODEL)


@st.cache_resource
def _client():
    return chromadb.PersistentClient(path=CHROMA_PATH)


def _coleccion(tema_id: int):
    # "cosine" => la distancia está entre 0 y 2, y similitud = 1 - distancia
    return _client().get_or_create_collection(f"tema_{tema_id}", metadata={"hnsw:space": "cosine"})


def indexar(tema_id: int, documentos: list[Document]) -> int:
    """Divide en chunks, calcula embeddings y guarda en Chroma. Devuelve # de chunks."""
    splitter = SentenceSplitter(chunk_size=800, chunk_overlap=100)
    nodos = splitter.get_nodes_from_documents(documentos)
    vector_store = ChromaVectorStore(chroma_collection=_coleccion(tema_id))
    storage = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodos, storage_context=storage, embed_model=_embed_model())
    return len(nodos)


def buscar(tema_id: int, consulta: str) -> list[dict]:
    """Fragmentos más parecidos a la consulta. Lista vacía si nada supera MIN_SCORE."""
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
    """Fragmentos al azar del tema (para generar quizzes y ejercicios variados)."""
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
