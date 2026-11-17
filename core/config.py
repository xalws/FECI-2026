import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # en la nube no existe; no pasa nada


def _get(nombre: str, defecto: str = "") -> str:
    # 1) variable de entorno / .env
    valor = os.getenv(nombre)
    # 2) Streamlit secrets (nube)
    if not valor:
        try:
            import streamlit as st
            if nombre in st.secrets:
                valor = st.secrets[nombre]
        except Exception:
            pass
    valor = str(valor).strip().strip('"').strip("'") if valor else ""
    return valor or defecto


def _float(nombre: str, defecto: float) -> float:
    try:
        return float(_get(nombre, str(defecto)))
    except ValueError:
        return defecto


def _normalizar_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("psql "):
        url = url[5:].strip().strip("'").strip('"')
    for prefijo in ("postgresql+psycopg://", "postgresql+psycopg2://",
                    "postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url


DATABASE_URL = _normalizar_url(_get("DATABASE_URL")) or f"sqlite:///{BASE_DIR / 'local.db'}"
GROQ_API_KEY = _get("GROQ_API_KEY")
GROQ_MODEL = _get("GROQ_MODEL", "openai/gpt-oss-120b")
# Modelo de respaldo si el principal llega a su cuota. Vacío = desactivado.
GROQ_MODEL_RESPALDO = _get("GROQ_MODEL_RESPALDO", "openai/gpt-oss-20b")

CHROMA_PATH = str(BASE_DIR / "chroma_data")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

TOP_K = 4                                # fragmentos recuperados por pregunta
MIN_SCORE = _float("MIN_SCORE", 0.25)    # similitud mínima
UMBRAL_TEMA = _float("UMBRAL_TEMA", 0.30)  # similitud mínima para asignar tema

ADMIN_EMAIL = _get("ADMIN_EMAIL", "admin@gmail.com")
ADMIN_PASSWORD = _get("ADMIN_PASSWORD", "admin123")