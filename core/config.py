import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get(nombre: str, defecto: str = "") -> str:
    valor = os.getenv(nombre)
    if valor:
        return valor
    try: 
        import streamlit as st
        return str(st.secrets.get(nombre, defecto))
    except Exception:
        return defecto


def _normalizar_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("psql "):
        url = url[5:].strip().strip("'").strip('"')
    for prefijo in ("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg2://" + url[len(prefijo):]
    return url

DATABASE_URL = _normalizar_url(_get("DATABASE_URL")) or f"sqlite:///{BASE_DIR / 'local.db'}"
GROQ_API_KEY = _get("GROQ_API_KEY")
GROQ_MODEL = _get("GROQ_MODEL", "openai/gpt-oss-120b")

CHROMA_PATH = str(BASE_DIR / "chroma_data")
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

 # fragmentos que se recuperan por pregunta
TOP_K = 4 
# similitud mínima 
MIN_SCORE = float(_get("MIN_SCORE", "0.25"))  

ADMIN_EMAIL = _get("ADMIN_EMAIL", "admin@gmail.com")
ADMIN_PASSWORD = _get("ADMIN_PASSWORD", "admin123")