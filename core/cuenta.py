"""Cuenta del usuario: validación, cambio y restablecimiento de contraseña."""
from sqlalchemy import select

from core import sesion
from core.db import get_session
from core.passwords import hash_password, verificar_password
from models.schema import Usuario

MIN_CARACTERES = 6
MAX_BYTES = 72  # límite de bcrypt: una contraseña más larga se rechaza en lugar de truncarse en silencio


def validar_password(password: str) -> str | None:
    # Devuelve el motivo si no sirve, o None si es válida.
    if len(password) < MIN_CARACTERES:
        return f"La contraseña debe tener al menos {MIN_CARACTERES} caracteres."
    if len(password.encode("utf-8")) > MAX_BYTES:
        return ("La contraseña es demasiado larga (el máximo son 72 bytes; los acentos, la ñ y los símbolos "
                "ocupan más de uno). Usa una más corta.")
    return None


def cambiar_password(usuario_id: int, actual: str, nueva: str, confirmacion: str,
                     conservar_token: str | None = None) -> tuple[bool, str]:
    # El propio usuario cambia su contraseña; debe conocer la actual. Las demás sesiones recordadas se cierran
    # (la de `conservar_token`, la de este navegador, sigue abierta).
    if nueva != confirmacion:
        return False, "La confirmación no coincide con la nueva contraseña."
    error = validar_password(nueva)
    if error:
        return False, error
    with get_session() as s:
        u = s.get(Usuario, usuario_id)
        if u is None or not u.activo:
            return False, "La cuenta no está disponible."
        if not verificar_password(actual, u.password_hash):
            return False, "La contraseña actual no es correcta."
        if actual == nueva:
            return False, "La nueva contraseña debe ser distinta de la actual."
        u.password_hash = hash_password(nueva)
    sesion.revocar_todas(usuario_id, conservar_token)
    return True, "Contraseña actualizada."


def restablecer_password(admin_id: int, usuario_id: int, nueva: str) -> tuple[bool, str]:
    # Un administrador fija una contraseña nueva a otro usuario (por ejemplo, si la olvidó).
    error = validar_password(nueva)
    if error:
        return False, error
    with get_session() as s:
        admin = s.get(Usuario, admin_id)
        if admin is None or admin.rol != "admin" or not admin.activo:
            return False, "Solo un administrador puede restablecer contraseñas."
        u = s.get(Usuario, usuario_id)
        if u is None:
            return False, "El usuario no existe."
        u.password_hash = hash_password(nueva)
        mensaje = f"Contraseña de {u.nombre} ({u.email}) restablecida."
    sesion.revocar_todas(usuario_id)  # quien la olvidó (o alguien más) pierde las sesiones que tuviera abiertas
    return True, mensaje


def restablecer_por_correo(email: str, nueva: str) -> tuple[bool, str]:
    # Para usar desde la terminal (scripts/restablecer_password.py): quien tiene acceso a la base de datos puede
    # restablecer cualquier cuenta, también la del administrador si la olvidó.
    error = validar_password(nueva)
    if error:
        return False, error
    with get_session() as s:
        u = s.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
        if u is None:
            return False, "No existe un usuario con ese correo."
        u.password_hash = hash_password(nueva)
        usuario_id, mensaje = u.id, f"Contraseña de {u.nombre} ({u.email}) restablecida."
    sesion.revocar_todas(usuario_id)
    return True, mensaje
