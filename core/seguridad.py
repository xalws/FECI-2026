"""Límite de intentos al iniciar sesión.

Después de `MAX_FALLOS` contraseñas incorrectas para un correo, ese correo queda bloqueado `VENTANA_MIN` minutos
contados desde el último fallo. Se guarda en la base (no en memoria) para que sobreviva a un reinicio de la app y valga
aunque haya varias copias corriendo. Cuenta igual los correos que no existen, así no se puede averiguar quién tiene cuenta.
"""
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from core import cache
from core.db import get_session
from models.schema import IntentoLogin

MAX_FALLOS = 5
VENTANA_MIN = 15


def _clave(email: str) -> str:
    return (email or "").strip().lower()[:200]


def _utc(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def fallos_recientes(email: str, ahora: datetime | None = None) -> tuple[int, datetime | None]:
    """(cuántos fallos tuvo el correo dentro de la ventana, fecha del último)."""
    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(minutes=VENTANA_MIN)
    with cache.sin_transaccion(), get_session() as s:  # se consulta en cada inicio de sesión: 1 viaje, no 3
        n, ultimo = s.execute(select(func.count(), func.max(IntentoLogin.fecha))
                              .where(IntentoLogin.email == _clave(email), IntentoLogin.fecha >= desde)).one()
    return n or 0, ultimo


def espera_por_fallos(n: int, ultimo: datetime | None, ahora: datetime | None = None) -> int:
    """Segundos de bloqueo que tocan con `n` fallos recientes, el último en `ultimo` (0 si no hay bloqueo)."""
    if n < MAX_FALLOS or ultimo is None:
        return 0
    ahora = ahora or datetime.now(timezone.utc)
    return max(0, math.ceil((_utc(ultimo) + timedelta(minutes=VENTANA_MIN) - ahora).total_seconds()))


def segundos_de_bloqueo(email: str, ahora: datetime | None = None) -> int:
    """Segundos que faltan para poder volver a intentar; 0 si el correo no está bloqueado."""
    return espera_por_fallos(*fallos_recientes(email, ahora), ahora)


def intentos_restantes(email: str, ahora: datetime | None = None) -> int:
    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(minutes=VENTANA_MIN)
    with get_session() as s:
        n = s.scalar(select(func.count()).where(IntentoLogin.email == _clave(email), IntentoLogin.fecha >= desde))
    return max(0, MAX_FALLOS - (n or 0))


def registrar_fallo(email: str) -> None:
    with get_session() as s:
        s.add(IntentoLogin(email=_clave(email)))
        # de paso se tira lo viejo, para que la tabla no crezca sin límite
        s.execute(delete(IntentoLogin).where(IntentoLogin.fecha < datetime.now(timezone.utc) - timedelta(days=1)))


def limpiar(email: str) -> None:
    """Al entrar bien se olvidan los fallos anteriores."""
    with get_session() as s:
        s.execute(delete(IntentoLogin).where(IntentoLogin.email == _clave(email)))


def texto_de_espera(segundos: int) -> str:
    minutos = -(-segundos // 60)  # hacia arriba: «1 minuto» y no «0»
    return f"{minutos} {'minuto' if minutos == 1 else 'minutos'}"
