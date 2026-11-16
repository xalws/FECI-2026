"""Debe importarse antes que cualquier módulo de core: apunta la app a una base SQLite temporal."""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

_dir = tempfile.mkdtemp(prefix="feci_tests_")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_dir) / "test.db").as_posix()
os.environ["GROQ_API_KEY"] = ""  # las pruebas nunca llaman a Groq
