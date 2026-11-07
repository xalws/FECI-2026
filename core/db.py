"""Conexión a la base de datos (PostgreSQL en Neon, o SQLite local si no hay DATABASE_URL)."""
from contextlib import contextmanager

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from core.config import ADMIN_EMAIL, ADMIN_PASSWORD, DATABASE_URL
from models.schema import Base, Usuario

# pool_pre_ping: Neon "duerme" las conexiones inactivas; esto las revisa antes de usarlas.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session():
    """Uso: with get_session() as s: ...  (hace commit al salir, rollback si hay error)."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db() -> None:
    """Crea las tablas si no existen y el primer administrador."""
    from core.passwords import hash_password

    Base.metadata.create_all(engine)
    with get_session() as s:
        hay_admin = s.scalar(select(Usuario.id).where(Usuario.rol == "admin").limit(1))
        if not hay_admin:
            s.add(Usuario(nombre="Administrador", email=ADMIN_EMAIL.lower(),
                          password_hash=hash_password(ADMIN_PASSWORD), rol="admin"))
