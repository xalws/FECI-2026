"""Repaso espaciado: las preguntas falladas vuelven a aparecer cada vez más separadas hasta que se dominan.

Cada pregunta que el alumno falló y nunca ha acertado se vuelve una «tarjeta». Al acertarla sube de caja y tarda más en
volver (1, 3, 7 y 14 días); al fallarla regresa a la primera caja y se ve al día siguiente. Tras acertarla en las
cuatro cajas se considera dominada y deja de salir. Las tarjetas son aparte de los exámenes: repasarlas no suma XP,
así que no se puede «inflar» el avance repitiendo las mismas preguntas.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from core.cache import memo
from core.db import get_session
from models.schema import Quiz, RespuestaQuiz, Tarjeta, Tema

INTERVALOS = [1, 3, 7, 14]  # días hasta volver a ver la tarjeta, según la caja en la que está
DOMINADA = len(INTERVALOS)


def siguiente(caja: int, correcta: bool, ahora: datetime) -> tuple[int, datetime | None]:
    """(caja nueva, cuándo vuelve a salir). Con `None` la tarjeta ya está dominada."""
    if not correcta:
        return 0, ahora + timedelta(days=INTERVALOS[0])
    nueva = min(DOMINADA, caja + 1)
    return nueva, (None if nueva >= DOMINADA else ahora + timedelta(days=INTERVALOS[nueva]))


def _utc(f: datetime) -> datetime:
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)  # SQLite devuelve las fechas sin zona


def _fallos_sin_tarjeta(s, alumno_id: int) -> list[tuple[int, datetime]]:
    """(pregunta, primer fallo) de lo que el alumno falló, nunca acertó y todavía no es tarjeta."""
    acertadas = select(RespuestaQuiz.quiz_id).where(RespuestaQuiz.alumno_id == alumno_id, RespuestaQuiz.es_correcta.is_(True))
    con_tarjeta = select(Tarjeta.quiz_id).where(Tarjeta.alumno_id == alumno_id)
    q = (select(RespuestaQuiz.quiz_id, func.min(RespuestaQuiz.fecha))
         .where(RespuestaQuiz.alumno_id == alumno_id, RespuestaQuiz.es_correcta.is_(False),
                RespuestaQuiz.quiz_id.not_in(acertadas), RespuestaQuiz.quiz_id.not_in(con_tarjeta))
         .group_by(RespuestaQuiz.quiz_id))
    return [(qid, _utc(f)) for qid, f in s.execute(q)]


def sincronizar(alumno_id: int) -> int:
    """Convierte en tarjeta cada pregunta fallada nueva (sale al día siguiente del fallo). Devuelve cuántas creó."""
    with get_session() as s:
        nuevas = _fallos_sin_tarjeta(s, alumno_id)
        for qid, fallo in nuevas:
            s.add(Tarjeta(alumno_id=alumno_id, quiz_id=qid, caja=0, proxima=fallo + timedelta(days=INTERVALOS[0])))
        return len(nuevas)


@memo(ttl=30)
def contar_pendientes(alumno_id: int) -> int:
    """Cuántas tarjetas toca ver hoy (incluye los fallos nuevos que ya cumplieron su primer día). Solo lee."""
    ahora = datetime.now(timezone.utc)
    with get_session() as s:
        listas = s.scalar(select(func.count()).select_from(Tarjeta).where(
            Tarjeta.alumno_id == alumno_id, Tarjeta.caja < DOMINADA, Tarjeta.proxima <= ahora))
        sin_crear = sum(1 for _, fallo in _fallos_sin_tarjeta(s, alumno_id) if fallo + timedelta(days=INTERVALOS[0]) <= ahora)
    return int(listas or 0) + sin_crear


def pendientes(alumno_id: int, limite: int = 15) -> list[dict]:
    """Las tarjetas que toca ver ahora, las más atrasadas primero, con su pregunta y opciones."""
    sincronizar(alumno_id)
    ahora = datetime.now(timezone.utc)
    with get_session() as s:
        filas = s.execute(
            select(Tarjeta, Quiz, Tema.nombre).join(Quiz, Quiz.id == Tarjeta.quiz_id).join(Tema, Tema.id == Quiz.tema_id)
            .where(Tarjeta.alumno_id == alumno_id, Tarjeta.caja < DOMINADA, Tarjeta.proxima <= ahora)
            .order_by(Tarjeta.proxima, Tarjeta.id).limit(limite)).all()
        return [{"id": t.id, "caja": t.caja, "pregunta": q.pregunta, "opciones": list(q.opciones), "tema": tema,
                 "dificultad": q.dificultad} for t, q, tema in filas]


def detalle(alumno_id: int, tarjeta_id: int) -> dict | None:
    """Una tarjeta del alumno con su pregunta y opciones (None si no existe o es de otra persona)."""
    with get_session() as s:
        fila = s.execute(select(Tarjeta, Quiz, Tema.nombre).join(Quiz, Quiz.id == Tarjeta.quiz_id)
                         .join(Tema, Tema.id == Quiz.tema_id)
                         .where(Tarjeta.id == tarjeta_id, Tarjeta.alumno_id == alumno_id)).first()
        if fila is None:
            return None
        t, q, tema = fila
        return {"id": t.id, "caja": t.caja, "pregunta": q.pregunta, "opciones": list(q.opciones), "tema": tema,
                "dificultad": q.dificultad}


def responder(alumno_id: int, tarjeta_id: int, indice: int, ahora: datetime | None = None) -> dict | None:
    """Registra la respuesta a una tarjeta. Devuelve el resultado, o None si la tarjeta no es de este alumno."""
    ahora = ahora or datetime.now(timezone.utc)
    with get_session() as s:
        t = s.get(Tarjeta, tarjeta_id)
        if t is None or t.alumno_id != alumno_id:
            return None
        q = s.get(Quiz, t.quiz_id)
        correcta = indice == q.indice_correcto
        t.caja, t.proxima = siguiente(t.caja, correcta, ahora)
        t.actualizada = ahora
        return {"correcta": correcta, "indice_correcto": q.indice_correcto, "explicacion": q.explicacion or "",
                "caja": t.caja, "dominada": t.caja >= DOMINADA, "proxima": t.proxima}


def resumen(alumno_id: int) -> dict:
    """Estado del repaso: por repasar hoy, en repaso, dominadas y cuándo vuelve la próxima."""
    sincronizar(alumno_id)
    ahora = datetime.now(timezone.utc)
    with get_session() as s:
        tarjetas = s.execute(select(Tarjeta.caja, Tarjeta.proxima).where(Tarjeta.alumno_id == alumno_id)).all()
    en_repaso = [(c, _utc(p)) for c, p in tarjetas if c < DOMINADA and p is not None]
    futuras = sorted(p for _, p in en_repaso if p > ahora)
    return {"hoy": sum(1 for _, p in en_repaso if p <= ahora), "en_repaso": len(en_repaso),
            "dominadas": sum(1 for c, _ in tarjetas if c >= DOMINADA), "proxima": futuras[0] if futuras else None}
