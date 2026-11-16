"""Registro de fallos de la app: se guardan en la base para que el administrador los vea en «Administración».

Registrar nunca debe romper nada: cualquier problema al guardar se ignora (queda en la consola). Los textos se limpian
antes de guardarse: contraseñas dentro de direcciones de base de datos y claves de API se tapan.
"""
import logging
import re
import traceback
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import delete, func, select

from core.db import get_session
from models.schema import ErrorApp

log = logging.getLogger("practic")
MAX_FILAS = 2000       # tope de la tabla: al pasarse se borran los más viejos
MAX_MENSAJE = 500
MAX_DETALLE = 4000

_SECRETOS = [
    (re.compile(r"(\w+://[^:/\s@]+:)[^@\s]+@"), r"\1***@"),           # postgresql://usuario:CLAVE@host
    (re.compile(r"\b(gsk|sk|pk|rk)[-_][A-Za-z0-9_\-]{12,}"), "***"),   # claves de API (Groq, OpenAI…)
    (re.compile(r"(?i)\b(api[_-]?key|token|password|contrase\w*|secret)(\s*[=:]\s*)\S+"), r"\1\2***"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-]+"), "Bearer ***"),
]


def limpiar(texto: str) -> str:
    for patron, reemplazo in _SECRETOS:
        texto = patron.sub(reemplazo, texto)
    return texto


def registrar(origen: str, error: BaseException, usuario_id: int | None = None) -> None:
    """Guarda el fallo `error` ocurrido en `origen` («tutor», «material», una página…)."""
    try:
        tipo = type(error).__name__
        mensaje = limpiar(str(error))[:MAX_MENSAJE]
        detalle = limpiar("".join(traceback.format_exception(type(error), error, error.__traceback__)))[-MAX_DETALLE:]
        tecnico = getattr(error, "detalle", "")  # los errores de la IA traen el texto técnico aparte
        if tecnico:
            detalle = f"{limpiar(str(tecnico))[:1000]}\n\n{detalle}"[-MAX_DETALLE:]
        log.error("%s: %s: %s", origen, tipo, mensaje)
        with get_session() as s:
            s.add(ErrorApp(origen=origen[:60], tipo=tipo[:80], mensaje=mensaje, detalle=detalle, usuario_id=usuario_id))
            total = s.scalar(select(func.count()).select_from(ErrorApp)) or 0
            if total > MAX_FILAS:
                corte = s.scalars(select(ErrorApp.id).order_by(ErrorApp.id.desc()).offset(MAX_FILAS - 1).limit(1)).first()
                if corte:
                    s.execute(delete(ErrorApp).where(ErrorApp.id < corte))
    except Exception:  # registrar el fallo no puede causar otro
        log.exception("No se pudo guardar el error en la base")


def recientes(dias: int = 7, origen: str | None = None, limite: int = 200) -> pd.DataFrame:
    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    q = select(ErrorApp).where(ErrorApp.fecha >= desde).order_by(ErrorApp.id.desc()).limit(limite)
    if origen:
        q = q.where(ErrorApp.origen == origen)
    with get_session() as s:
        filas = [{"id": e.id, "fecha": e.fecha if e.fecha.tzinfo else e.fecha.replace(tzinfo=timezone.utc),
                  "origen": e.origen, "tipo": e.tipo, "mensaje": e.mensaje, "detalle": e.detalle,
                  "usuario_id": e.usuario_id} for e in s.scalars(q)]
    return pd.DataFrame(filas, columns=["id", "fecha", "origen", "tipo", "mensaje", "detalle", "usuario_id"])


def por_tipo(dias: int = 7) -> pd.DataFrame:
    """Cuántas veces ocurrió cada fallo distinto en los últimos días (los que más se repiten, primero)."""
    df = recientes(dias, limite=MAX_FILAS)
    if df.empty:
        return pd.DataFrame(columns=["origen", "tipo", "veces", "último", "mensaje"])
    g = (df.groupby(["origen", "tipo"]).agg(veces=("id", "count"), ultimo=("fecha", "max"), mensaje=("mensaje", "first"))
         .reset_index().rename(columns={"ultimo": "último"}))
    return g.sort_values(["veces", "último"], ascending=False).reset_index(drop=True)


def borrar_anteriores(dias: int) -> int:
    """Borra los fallos con más de `dias` días (0 = todos). Devuelve cuántos."""
    with get_session() as s:
        q = delete(ErrorApp)
        if dias > 0:
            q = q.where(ErrorApp.fecha < datetime.now(timezone.utc) - timedelta(days=dias))
        return s.execute(q).rowcount or 0
