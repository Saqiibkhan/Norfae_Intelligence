from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.dependencies import get_current_user
from app.core.security import PasswordValidationError, SecurityManager
from app.core.tokens import (
    InvalidAccessToken,
    TokenConfigurationError,
    create_access_token,
    decode_access_token,
    get_user_id_from_token,
)
from app.models.user_model import User
from app.schemas.auth_schema import AuthenticatedUserResponse, TokenResponse

TEST_JWT_SECRET = "local-test-key-that-is-at-least-32-bytes-long"


@pytest.fixture
def configured_jwt(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", SecretStr(TEST_JWT_SECRET))
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30)


@pytest.fixture
def user_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    User.__table__.create(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        User.__table__.drop(engine)
        engine.dispose()


def signed_test_token(payload, key=TEST_JWT_SECRET, algorithm="HS256"):
    return jwt.encode(payload, key, algorithm=algorithm)


def test_password_hashing_and_verification():
    password = "Correct horse battery staple!"
    password_hash = SecurityManager.hash_password(password)

    assert password_hash != password
    assert password_hash.startswith("$2b$")
    assert SecurityManager.verify_password(password, password_hash)
    assert not SecurityManager.verify_password("incorrect password", password_hash)


def test_password_validation_and_malformed_hash_handling():
    with pytest.raises(PasswordValidationError):
        SecurityManager.hash_password("too-short")
    with pytest.raises(PasswordValidationError, match="72 UTF-8 bytes"):
        SecurityManager.hash_password("é" * 37)

    assert not SecurityManager.verify_password("password-long-enough", "not-a-hash")
    assert not SecurityManager.verify_password("x" * 73, "$2b$12$invalid")


def test_token_creation_and_valid_decoding(configured_jwt):
    token = create_access_token(123)
    claims = decode_access_token(token)

    assert get_user_id_from_token(token) == 123
    assert claims["sub"] == "123"
    assert claims["token_use"] == "access"
    assert "password" not in claims
    assert "password_hash" not in claims
    assert TokenResponse(access_token=token, expires_in=1800).token_type == "bearer"


def test_expired_token_is_rejected(configured_jwt):
    now = datetime.now(timezone.utc)
    token = signed_test_token(
        {
            "sub": "1",
            "token_use": "access",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        }
    )

    with pytest.raises(InvalidAccessToken):
        decode_access_token(token)


def test_invalid_signature_malformed_token_and_bad_subject_are_rejected(
    configured_jwt,
):
    valid_claims = {
        "sub": "1",
        "token_use": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    wrong_signature = signed_test_token(valid_claims, key="another-key-that-is-long-enough-123")
    missing_subject = signed_test_token(
        {
            "token_use": "access",
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
    )
    invalid_subject = signed_test_token({**valid_claims, "sub": "not-a-user-id"})

    for token in (wrong_signature, "not.a.jwt", missing_subject, invalid_subject):
        with pytest.raises(InvalidAccessToken):
            decode_access_token(token)


def test_missing_jwt_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", None)

    with pytest.raises(TokenConfigurationError):
        create_access_token(1)


def test_production_jwt_configuration_requires_a_distinct_strong_secret():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DATABASE_URL="sqlite://", APP_ENV="production")

    secure_secret = "a-random-production-secret-value-over-32-bytes"
    configured = Settings(
        _env_file=None,
        DATABASE_URL="sqlite://",
        APP_ENV="production",
        JWT_SECRET_KEY=secure_secret,
        OPENROUTER_API_KEY=SecretStr("different-openrouter-key"),
    )
    assert configured.JWT_SECRET_KEY.get_secret_value() == secure_secret

    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="sqlite://",
            APP_ENV="production",
            JWT_SECRET_KEY="replace-this-with-a-random-value-xxxxxxxx",
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            DATABASE_URL="sqlite://",
            APP_ENV="production",
            JWT_SECRET_KEY="a-random-production-secret-value-over-32-bytes",
            OPENROUTER_API_KEY=SecretStr(
                "a-random-production-secret-value-over-32-bytes"
            ),
        )


def test_missing_token_is_rejected_with_bearer_challenge(user_session):
    with pytest.raises(HTTPException) as exc:
        get_current_user(None, user_session)

    assert exc.value.status_code == 401
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_current_user_dependency_rejects_invalid_and_expired_tokens(
    configured_jwt, user_session
):
    now = datetime.now(timezone.utc)
    expired = signed_test_token(
        {
            "sub": "1",
            "token_use": "access",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
        }
    )
    for token in ("not.a.jwt", expired):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials, user_session)
        assert exc.value.status_code == 401


def test_inactive_and_missing_users_are_rejected(configured_jwt, user_session):
    inactive = User(
        email="inactive@example.com",
        password_hash="already-hashed",
        is_active=False,
    )
    user_session.add(inactive)
    user_session.commit()

    for user_id in (inactive.id, 9999):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=create_access_token(user_id)
        )
        with pytest.raises(HTTPException) as exc:
            get_current_user(credentials, user_session)
        assert exc.value.status_code == 401


def test_current_user_dependency_uses_only_verified_token_subject(
    configured_jwt, user_session
):
    user = User(
        email="active@example.com",
        password_hash="already-hashed",
        is_active=True,
    )
    user_session.add(user)
    user_session.commit()
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_access_token(user.id)
    )

    current = get_current_user(credentials, user_session)
    response = AuthenticatedUserResponse.model_validate(current)

    assert current.id == user.id
    assert "password_hash" not in response.model_dump()
