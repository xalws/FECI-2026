"""Guarda un respaldo de la base en la carpeta `respaldos/` y conserva los últimos N.

Uso (desde la carpeta del proyecto, con el entorno virtual activo):
    python scripts/respaldo.py                 # respaldo completo
    python scripts/respaldo.py --sin-vectores  # más ligero: sin los vectores del material (se recalculan al resubir PDF)
    python scripts/respaldo.py --conservar 20  # cuántos respaldos guardar (por defecto 10)
Se puede programar con el Programador de tareas de Windows para que corra cada día.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from core import respaldo  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sin-vectores", action="store_true", help="no incluye la columna embedding de los fragmentos")
    p.add_argument("--conservar", type=int, default=10, help="cuántos respaldos dejar en la carpeta (por defecto 10)")
    args = p.parse_args()

    carpeta = RAIZ / "respaldos"
    carpeta.mkdir(exist_ok=True)
    contenido, manifiesto = respaldo.crear(incluir_vectores=not args.sin_vectores)
    destino = carpeta / f"respaldo_{datetime.now():%Y-%m-%d_%H%M}.zip"
    destino.write_bytes(contenido)
    total = sum(manifiesto["filas"].values())
    print(f"Respaldo guardado: {destino} ({len(contenido) / 1024:.0f} KB, {total} filas en {len(manifiesto['filas'])} tablas)")
    viejos = sorted(carpeta.glob("respaldo_*.zip"))[:-max(1, args.conservar)]
    for v in viejos:
        v.unlink()
    if viejos:
        print(f"Se borraron {len(viejos)} respaldos antiguos.")


if __name__ == "__main__":
    main()
