"""Subida de material: un PDF de toda la materia que se reparte entre los temas de su retícula."""
from sqlalchemy import func, select

from core import pdf_loader, rag, reticula
from core.db import get_session
from models.schema import Documento, Fragmento


def ya_subido(materia_id: int, nombre_archivo: str) -> bool:
    ids = [t["id"] for t in reticula.temas_de_materia(materia_id)]
    if not ids:
        return False
    with get_session() as s:
        return s.scalar(select(Documento.id).where(Documento.tema_id.in_(ids),
                                                   Documento.nombre_archivo == nombre_archivo)) is not None


def cobertura(materia_id: int) -> list[dict]:
    # Por cada tema de la retícula: cuántos fragmentos reales tiene y qué documentos hay registrados.
    # estado: «ok» (con material), «sin_material» (nada) o «sin_indice» (hay un documento registrado pero sus
    # fragmentos no están en la base, p. ej. porque se subió antes de que el índice fuera compartido).
    temas = reticula.temas_de_materia(materia_id)
    if not temas:
        return []
    ids = [t["id"] for t in temas]
    with get_session() as s:
        fragmentos = dict(s.execute(select(Fragmento.tema_id, func.count()).where(Fragmento.tema_id.in_(ids))
                                    .group_by(Fragmento.tema_id)).all())
        docs: dict[int, list] = {}
        for d in s.scalars(select(Documento).where(Documento.tema_id.in_(ids)).order_by(Documento.id)):
            docs.setdefault(d.tema_id, []).append({"id": d.id, "archivo": d.nombre_archivo, "fecha": d.fecha})
    filas = []
    for t in temas:
        n, documentos = fragmentos.get(t["id"], 0), docs.get(t["id"], [])
        estado = "ok" if n else ("sin_indice" if documentos else "sin_material")
        filas.append({"tema_id": t["id"], "tema": t["nombre"], "unidad": t["unidad"], "fragmentos": n,
                      "documentos": documentos, "estado": estado})
    return filas


def eliminar_archivo(materia_id: int, nombre_archivo: str) -> int:
    # Borra un PDF de la materia (sus documentos y fragmentos en todos los temas). Devuelve cuántos documentos.
    ids = [t["id"] for t in reticula.temas_de_materia(materia_id)]
    with get_session() as s:
        docs = s.scalars(select(Documento).where(Documento.tema_id.in_(ids),
                                                 Documento.nombre_archivo == nombre_archivo)).all()
        for d in docs:
            rag.eliminar_documento(d.tema_id, d.id)
            s.delete(d)
        return len(docs)


def subir_a_materia(archivo, nombre_archivo: str, materia_id: int, maestro_id: int) -> dict:
    # Lee el PDF, asigna cada fragmento al tema de la retícula que mejor lo describe y lo indexa ahí.
    # Devuelve {"por_tema": {nombre del tema: fragmentos}, "sin_tema": fragmentos sin tema claro}.
    temas = reticula.temas_de_materia(materia_id)
    if not temas:
        raise ValueError("Esta materia todavía no tiene temas. Primero sube su retícula.")
    nombres = {t["id"]: t["nombre"] for t in temas}
    paginas = pdf_loader.extraer_documentos(archivo, 0, 0, nombre_archivo)
    por_tema, sin_tema = rag.repartir_por_temas(rag.partir(paginas), temas)
    resultado: dict[str, int] = {}
    for tema_id, nodos in por_tema.items():
        with get_session() as s:
            doc = Documento(tema_id=tema_id, maestro_id=maestro_id, nombre_archivo=nombre_archivo, num_chunks=0)
            s.add(doc)
            s.flush()
            doc_id = doc.id
        for nodo in nodos:
            nodo.metadata["tema_id"], nodo.metadata["documento_id"] = tema_id, doc_id
        try:
            cantidad = rag.indexar_nodos(tema_id, nodos)
        except Exception:
            rag.eliminar_documento(tema_id, doc_id)  # limpia lo que haya quedado en Chroma
            with get_session() as s:
                s.delete(s.get(Documento, doc_id))
            raise
        with get_session() as s:
            s.get(Documento, doc_id).num_chunks = cantidad
        resultado[nombres[tema_id]] = cantidad
    return {"por_tema": resultado, "sin_tema": sin_tema}
