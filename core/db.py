from contextlib import contextmanager

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from core.config import ADMIN_EMAIL, ADMIN_PASSWORD, DATABASE_URL
from models.schema import Base, Usuario

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def get_session():
    # Commit al salir, rollback si hay error
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def _migrar() -> None:
    columnas = {c["name"] for c in inspect(engine).get_columns("usuarios")}
    if "cuatrimestre_id" not in columnas:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE usuarios ADD COLUMN cuatrimestre_id INTEGER REFERENCES cuatrimestres(id)"))


def init_db() -> None:
    from core.passwords import hash_password

    Base.metadata.create_all(engine)
    _migrar()
    with get_session() as s:
        hay_admin = s.scalar(select(Usuario.id).where(Usuario.rol == "admin").limit(1))
        if not hay_admin:
            s.add(Usuario(nombre="Administrador", email=ADMIN_EMAIL.lower(),
                          password_hash=hash_password(ADMIN_PASSWORD), rol="admin"))
