"""Respaldo de la base: un .zip con una tabla por archivo (una fila JSON por línea) y un manifiesto.

Sirve para no depender de un solo servidor. Incluye TODO lo que hay en la base, también los códigos cifrados de las
contraseñas y las sesiones, así que hay que guardarlo como se guardaría la base misma (no se sube a git ni se comparte).
Para restaurar, cada línea es una fila con los nombres de columna de la tabla; los textos de fecha están en ISO 8601.
"""
import base64
import json
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO

from sqlalchemy import select

from core.db import get_session
from models.schema import Base

FORMATO = 1


def _serializable(valor):
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, bytes):
        return base64.b64encode(valor).decode("ascii")
    if isinstance(valor, Decimal):
        return float(valor)
    return str(valor)


def crear(incluir_vectores: bool = True) -> tuple[bytes, dict]:
    """Devuelve (contenido del .zip, manifiesto con las filas de cada tabla).

    Sin vectores (`incluir_vectores=False`) los fragmentos de material se guardan sin su columna `embedding`, que es
    lo más pesado y se puede volver a calcular al volver a subir los PDF.
    """
    salida = BytesIO()
    filas_por_tabla: dict[str, int] = {}
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as z, get_session() as s:
        for tabla in Base.metadata.sorted_tables:
            columnas = [c for c in tabla.columns if incluir_vectores or c.name != "embedding"]
            lineas = [json.dumps({c.name: v for c, v in zip(columnas, fila)}, ensure_ascii=False, default=_serializable)
                      for fila in s.execute(select(*columnas))]
            z.writestr(f"{tabla.name}.jsonl", "\n".join(lineas) + ("\n" if lineas else ""))
            filas_por_tabla[tabla.name] = len(lineas)
        manifiesto = {"formato": FORMATO, "creado": datetime.now(timezone.utc).isoformat(), "con_vectores": incluir_vectores,
                      "filas": filas_por_tabla}
        z.writestr("manifiesto.json", json.dumps(manifiesto, ensure_ascii=False, indent=1))
    return salida.getvalue(), manifiesto
