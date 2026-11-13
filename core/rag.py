"""Búsqueda por significado en el material de cada tema.

Los fragmentos y sus vectores se guardan en la tabla `fragmentos` de la base de datos (la misma que comparte todo el
equipo), y la similitud se calcula con numpy. Con las decenas o cientos de fragmentos que tiene un tema es
instantáneo; si algún día fueran decenas de miles, convendría pasar a pgvector.
"""
import random

import numpy as np
import streamlit as st
from llama_index.core import Document
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode
from llama_index.embeddings.fastembed import FastEmbedEmbedding
from sqlalchemy import delete, func, select

from core.config import EMBED_MODEL, MIN_SCORE, TOP_K, UMBRAL_TEMA
from core.db import get_session
from models.schema import Fragmento


@st.cache_resource(show_spinner="Cargando modelo (la primera vez descarga ~200 MB)...")
def _embed_model():
    return FastEmbedEmbedding(model_name=EMBED_MODEL)


def partir(documentos: list[Document]) -> list:
    return SentenceSplitter(chunk_size=800, chunk_overlap=100).get_nodes_from_documents(documentos)


def _a_entero(valor) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def indexar_nodos(tema_id: int, nodos: list) -> int:
    if not nodos:
        return 0
    # PostgreSQL no acepta el carácter nulo (0x00), que algunos PDF traen al extraer el texto
    textos = [n.get_content(metadata_mode=MetadataMode.NONE).replace("\x00", "") for n in nodos]
    vectores = _embed_model().get_text_embedding_batch(textos)
    with get_session() as s:
        s.add_all([Fragmento(tema_id=tema_id, documento_id=_a_entero(n.metadata.get("documento_id")), texto=t,
                             archivo=str(n.metadata.get("archivo", "")), pagina=_a_entero(n.metadata.get("pagina")),
                             embedding=[float(x) for x in v])
                   for n, t, v in zip(nodos, textos, vectores)])
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
    with get_session() as s:
        filas = s.execute(select(Fragmento.texto, Fragmento.archivo, Fragmento.pagina, Fragmento.embedding)
                          .where(Fragmento.tema_id == tema_id)).all()
    if not filas:
        return []
    vector = np.asarray(_embed_model().get_query_embedding(consulta), dtype=float)
    matriz = np.asarray([f[3] for f in filas], dtype=float)
    similitud = (matriz @ vector) / (np.linalg.norm(matriz, axis=1) * np.linalg.norm(vector) + 1e-12)
    orden = np.argsort(-similitud)[:TOP_K]
    return [{"texto": filas[i][0], "score": float(similitud[i]), "archivo": filas[i][1],
             "pagina": filas[i][2] if filas[i][2] is not None else ""}
            for i in orden if similitud[i] >= MIN_SCORE]


def chunks_aleatorios(tema_id: int, n: int = 3) -> list[dict]:
    with get_session() as s:
        textos = list(s.scalars(select(Fragmento.texto).where(Fragmento.tema_id == tema_id)))
    return [{"texto": t, "score": 1.0, "archivo": "", "pagina": ""} for t in random.sample(textos, min(n, len(textos)))]


def eliminar_documento(tema_id: int, documento_id: int) -> None:
    with get_session() as s:
        s.execute(delete(Fragmento).where(Fragmento.tema_id == tema_id, Fragmento.documento_id == documento_id))


def eliminar_temas(tema_ids: list[int]) -> None:
    if tema_ids:
        with get_session() as s:
            s.execute(delete(Fragmento).where(Fragmento.tema_id.in_(tema_ids)))


def total_chunks(tema_id: int) -> int:
    with get_session() as s:
        return s.scalar(select(func.count()).select_from(Fragmento).where(Fragmento.tema_id == tema_id)) or 0
