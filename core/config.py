"""Configuración central: lee variables del archivo .env (o de st.secrets si despliegas)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(nombre: str, defecto: str = "") -> str:
    valor = os.getenv(nombre)
    if valor:
        return valor
    try:  # st.secrets existe al desplegar en Streamlit Cloud
        import streamlit as st

        return str(st.secrets.get(nombre, defecto))
    except Exception:
        return defecto


def _normalizar_url(url: str) -> str:
    """Fuerza el driver psycopg2 (el que instala requirements.txt) para PostgreSQL."""
    url = url.strip().strip('"').strip("'")
    if url.startswith("psql "):  # Neon a veces muestra: psql 'postgresql://...'
        url = url[5:].strip().strip("'").strip('"')
    for prefijo in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url


DATABASE_URL = _normalizar_url(_get("DATABASE_URL")) or f"sqlite:///{BASE_DIR / 'local.db'}"
GROQ_API_KEY = _get("GROQ_API_KEY")
GROQ_MODEL = _get("GROQ_MODEL", "openai/gpt-oss-120b")  # llama-3.3-70b fue retirado en el plan gratuito

CHROMA_PATH = str(BASE_DIR / "chroma_data")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"  # soporta español

TOP_K = 4  # fragmentos que se recuperan por pregunta
MIN_SCORE = float(_get("MIN_SCORE", "0.25"))  # similitud mínima (0-1); abajo de esto NO se llama al LLM

ADMIN_EMAIL = _get("ADMIN_EMAIL", "admin@demo.com")
ADMIN_PASSWORD = _get("ADMIN_PASSWORD", "admin123")
