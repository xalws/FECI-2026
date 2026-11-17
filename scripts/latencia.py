"""Mide cuánto tarda la base de datos en responder (útil para comparar regiones o conexiones).

Uso: python scripts/latencia.py
Cada pantalla de la app hace decenas de consultas: a ~70 ms por consulta (base en otra región) una pantalla tarda
segundos; a ~5 ms (base en la misma región que la app) apenas se nota.
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.db import engine  # noqa: E402


def main(n: int = 15) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))  # abre la conexión (no cuenta)
        tiempos = []
        for _ in range(n):
            t = time.perf_counter()
            conn.execute(text("SELECT 1"))
            tiempos.append((time.perf_counter() - t) * 1000)
    mediana = statistics.median(tiempos)
    print(f"Ida y vuelta a la base: mediana {mediana:.0f} ms (mínimo {min(tiempos):.0f}, máximo {max(tiempos):.0f}) en {n} consultas")
    if mediana > 40:
        con_pooler = "-pooler" in (engine.url.host or "")
        print("Es alta: la app y la base probablemente están lejos. "
              + ("Ya se usa el conector con pooler, así que solo una región más cercana (o poner la app en la misma "
                 "región que la base) reduciría el tiempo de cada pantalla." if con_pooler else
                 "Una región más cercana o el conector con pooler de la base reducirían el tiempo de cada pantalla."))
    else:
        print("Es baja: la distancia a la base no es el problema.")


if __name__ == "__main__":
    main()
