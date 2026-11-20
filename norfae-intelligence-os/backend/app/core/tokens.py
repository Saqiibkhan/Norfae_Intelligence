from datetime import datetime, timedelta, timezone

import jwt
from pydantic import SecretStr

from app.core.config import settings


class InvalidAccessToken(ValueError):
    """Raised when an access token is missing required valid claims."""


class TokenConfigurationError(RuntimeError):
    """Raised when token signing is not safely configured."""


def _signing_key() -> str:
    secret: SecretStr | None = settings.JWT_SECRET_KEY
    if secret is None:
        raise TokenConfigurationError("JWT signing is not configured.")
    key = secret.get_secret_value()
    if len(key.encode("utf-8")) < 32:
        raise TokenConfigurationError("JWT signing key must contain at least 32 bytes.")
    openrouter_secret = settings.OPENROUTER_API_KEY
    if openrouter_secret is not None and key == openrouter_secret.get_secret_value():
        raise TokenConfigurationError("JWT signing key must be separate from API keys.")
    if settings.JWT_ALGORITHM != "HS256":
        raise TokenConfigurationError("Configured JWT algorithm is not supported.")
    return key


def _normalize_user_id(user_id: int | str) -> str:
    if isinstance(user_id, bool):
        raise ValueError("User ID must be a positive integer.")
    try:
        normalized = int(user_id)
    except (TypeError, ValueError):
        raise ValueError("User ID must be a positive integer.") from None
    if normalized <= 0 or str(normalized) != str(user_id).strip():
        raise ValueError("User ID must be a positive integer.")
    return str(normalized)


def create_access_token(user_id: int | str) -> str:
    subject = _normalize_user_id(user_id)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "iat": now, "exp": expires_at, "token_use": "access"}
    return jwt.encode(payload, _signing_key(), algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    if not isinstance(token, str) or not token:
        raise InvalidAccessToken("Invalid access token.")
    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "token_use"]},
        )
    except (jwt.PyJWTError, TypeError, ValueError) as error:
        raise InvalidAccessToken("Invalid access token.") from error

    if payload.get("token_use") != "access":
        raise InvalidAccessToken("Invalid access token.")
    try:
        _normalize_user_id(payload.get("sub"))
    except ValueError as error:
        raise InvalidAccessToken("Invalid access token.") from error
    return payload


def get_user_id_from_token(token: str) -> int:
    payload = decode_access_token(token)
    return int(payload["sub"])
