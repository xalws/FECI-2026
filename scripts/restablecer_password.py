"""Restablece la contraseña de una cuenta desde la terminal (por ejemplo, la del administrador si la olvidó).

Uso, desde la carpeta del proyecto y con el venv activo:
    python scripts/restablecer_password.py correo@ejemplo.com

Pide la nueva contraseña sin mostrarla en pantalla. Escribe en la base de datos de DATABASE_URL, así que solo
puede usarlo quien tenga acceso a ella.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import cuenta  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Uso: python scripts/restablecer_password.py correo@ejemplo.com")
    correo = sys.argv[1]
    nueva = getpass.getpass("Nueva contraseña: ")
    if nueva != getpass.getpass("Confirma la nueva contraseña: "):
        sys.exit("Las contraseñas no coinciden. No se cambió nada.")
    ok, mensaje = cuenta.restablecer_por_correo(correo, nueva)
    print(mensaje)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
