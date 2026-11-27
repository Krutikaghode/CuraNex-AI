"""Password hashing (Argon2 via pwdlib) and JWT access tokens (PyJWT)."""

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"
DEV_SECRET = "dev-only-insecure-secret-change-me-before-deploying"
_hasher = PasswordHash.recommended()
# Verified against when the email is unknown, so response time does not reveal which
# emails exist.
_DUMMY_HASH = _hasher.hash("not-a-real-password")


class InvalidTokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.jwt_expire_minutes * 60
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires_in


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp"]}
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as error:
        raise InvalidTokenError("Invalid or expired token.") from error


def check_secret_is_safe() -> None:
    settings = get_settings()
    if settings.environment != "development" and (
        settings.jwt_secret == DEV_SECRET or len(settings.jwt_secret) < 32
    ):
        raise RuntimeError(
            "Set CURANEX_JWT_SECRET to a random value of at least 32 characters "
            "outside development (e.g. `openssl rand -hex 32`)."
        )
