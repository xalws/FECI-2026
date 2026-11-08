import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        return False
