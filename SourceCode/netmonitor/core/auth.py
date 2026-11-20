"""Accounts: salted PBKDF2 password hashes. Passwords are never stored or logged as text."""
import hashlib
import hmac
import os

from netmonitor import config


def hash_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Return (salt, hash). A new random salt makes two equal passwords hash differently."""
    salt = salt or os.urandom(16)
    return salt, hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, config.AUTH_ITERATIONS)


def verify_password(password: str, salt: bytes, digest: bytes) -> bool:
    """compare_digest takes the same time wherever the bytes differ, so timing reveals nothing."""
    return hmac.compare_digest(hash_password(password, salt)[1], digest)


def check_new_password(username: str, password: str, confirm: str):
    """Raise ValueError with a message for the form if the new password is not acceptable."""
    if len(password) < config.PASSWORD_MIN_LEN:
        raise ValueError(f"The password needs at least {config.PASSWORD_MIN_LEN} characters.")
    if password.lower() == username.lower():
        raise ValueError("The password cannot be the same as the username.")
    if password != confirm:
        raise ValueError("The two passwords do not match.")