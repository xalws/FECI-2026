"""Copia a la base de datos compartida el material que estaba en la carpeta local chroma_data.

Uso, desde la carpeta del proyecto y con el venv activo:
    python scripts/migrar_chroma_a_bd.py

Es seguro repetirlo: los temas que ya tienen fragmentos en la base se saltan. No borra chroma_data.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from core.config import CHROMA_PATH  # noqa: E402
from core.db import get_session, init_db  # noqa: E402
from models.schema import Fragmento, Tema  # noqa: E402


def entero(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def main() -> None:
    init_db()
    if not Path(CHROMA_PATH).exists():
        print(f"No hay carpeta {CHROMA_PATH}; no hay nada que migrar.")
        return
    cliente = chromadb.PersistentClient(path=CHROMA_PATH)
    with get_session() as s:
        temas_validos = set(s.scalars(select(Tema.id)))
    copiados = saltados = huerfanos = 0
    for col in sorted(cliente.list_collections(), key=lambda c: c.name):
        if not col.name.startswith("tema_"):
            continue
        tema_id = int(col.name.split("_", 1)[1])
        if tema_id not in temas_validos:
            huerfanos += 1
            continue
        with get_session() as s:
            ya = s.scalar(select(func.count()).select_from(Fragmento).where(Fragmento.tema_id == tema_id))
        if ya:
            saltados += 1
            continue
        datos = col.get(include=["documents", "metadatas", "embeddings"])
        with get_session() as s:
            for texto, meta, emb in zip(datos["documents"], datos["metadatas"], datos["embeddings"]):
                meta = meta or {}
                s.add(Fragmento(tema_id=tema_id, documento_id=entero(meta.get("documento_id")),
                                texto=texto.replace("\x00", ""),  # PostgreSQL no acepta el carácter nulo
                                archivo=str(meta.get("archivo", "")), pagina=entero(meta.get("pagina")),
                                embedding=[float(x) for x in emb]))
        copiados += len(datos["documents"])
        print(f"  tema {tema_id}: {len(datos['documents'])} fragmento(s)")
    print(f"\nListo: {copiados} fragmentos copiados | temas ya migrados: {saltados} | "
          f"colecciones de temas que ya no existen (ignoradas): {huerfanos}")


if __name__ == "__main__":
    main()
