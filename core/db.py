import time
from contextlib import contextmanager

from sqlalchemy import create_engine, event, exc, inspect, select, text
from sqlalchemy.orm import sessionmaker

from core import cache
from core.config import ADMIN_EMAIL, ADMIN_PASSWORD, DATABASE_URL
from models.schema import Base, Usuario

# Con la red inestable, una conexión cortada sin aviso dejaba la consulta esperando minutos (la pantalla «se quedaba
# cargando»). Estos límites hacen que se detecte en segundos: el error se ve y las lecturas se reintentan solas.
LIMITES_DE_RED = {
    "connect_timeout": 10,       # segundos para abrir la conexión
    "keepalives": 1,             # sondas TCP para notar una conexión muerta aunque no se esté usando
    "keepalives_idle": 20,
    "keepalives_interval": 5,
    "keepalives_count": 3,
    "tcp_user_timeout": 20000,   # ms: si lo enviado no se confirma en este tiempo, la conexión se da por perdida
}
engine = create_engine(DATABASE_URL, pool_recycle=300,
                       connect_args=LIMITES_DE_RED if DATABASE_URL.startswith("postgresql") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Con `pool_pre_ping` cada vez que se toma una conexión se hace un viaje extra a la base (con una base remota son
# ~70 ms de más por consulta inicial). Aquí solo se comprueba la conexión cuando estuvo sin usarse un rato, que es
# cuando el servidor pudo cerrarla; si ya no sirve, SQLAlchemy abre otra sin que el usuario vea un error.
REVISAR_TRAS_SEGUNDOS = 30


@event.listens_for(engine, "before_cursor_execute")
def _marcar_escritura(conn, _cursor, sentencia, _params, _ctx, _many) -> None:
    if cache.es_escritura(sentencia):
        conn.info["escribio"] = True
        conn.info.setdefault("tablas", set()).add(cache.tabla_de(sentencia) or "*")


@event.listens_for(engine, "commit")
def _tras_confirmar(conn) -> None:
    # La caché de lecturas se vacía cuando la escritura ya es visible para los demás, no antes
    tablas = conn.info.pop("tablas", set())
    if conn.info.pop("escribio", False):
        cache.invalidar(None if "*" in tablas else tablas)


@event.listens_for(engine, "rollback")
def _tras_deshacer(conn) -> None:
    # Si la conexión se cortó, leer `conn.info` lanza otro error que tapaba el original: se ignora (se descarta igual)
    try:
        conn.info.pop("escribio", None)
        conn.info.pop("tablas", None)
    except exc.SQLAlchemyError:
        pass


@event.listens_for(engine, "checkout")
def _revisar_conexion(dbapi_conn, registro, _proxy) -> None:
    ahora = time.monotonic()
    if ahora - registro.info.get("ultimo_uso", 0.0) > REVISAR_TRAS_SEGUNDOS:
        try:
            cur = dbapi_conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
        except Exception as e:
            raise exc.DisconnectionError(str(e)) from e
    registro.info["ultimo_uso"] = ahora


# Misma conexión y mismas reglas, pero sin transacción: para las lecturas guardadas con `@memo` (ver core/cache.py)
engine_lectura = engine.execution_options(isolation_level="AUTOCOMMIT")
SessionLectura = sessionmaker(bind=engine_lectura, expire_on_commit=False)


@contextmanager
def get_session():
    # Commit al salir, rollback si hay error. Dentro de una lectura guardada (`@memo`) no se abre transacción.
    s = SessionLectura() if cache.modo_lectura.get() else SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# (tabla, columna, definición) de columnas agregadas después de crear las tablas
COLUMNAS_NUEVAS = [
    ("usuarios", "cuatrimestre_id", "INTEGER REFERENCES cuatrimestres(id)"),
    ("temas", "objetivos", "TEXT"),
    ("quizzes", "dificultad", "INTEGER"),
    ("conversaciones", "tipo", "VARCHAR(20)"),
    ("usuarios", "meta_diaria_min", "INTEGER"),
    ("usuarios", "vitrina", "TEXT"),
    ("avisos", "tarea_id", "INTEGER"),
    ("tareas", "visible_desde", "TIMESTAMP WITH TIME ZONE"),
]


def _migrar() -> None:
    insp = inspect(engine)
    for tabla, columna, definicion in COLUMNAS_NUEVAS:
        if columna not in {c["name"] for c in insp.get_columns(tabla)}:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}"))


def init_db() -> None:
    from core.passwords import hash_password

    Base.metadata.create_all(engine)
    _migrar()
    with get_session() as s:
        hay_admin = s.scalar(select(Usuario.id).where(Usuario.rol == "admin").limit(1))
        if not hay_admin:
            s.add(Usuario(nombre="Administrador", email=ADMIN_EMAIL.lower(),
                          password_hash=hash_password(ADMIN_PASSWORD), rol="admin"))
