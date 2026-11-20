from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.tokens import (
    InvalidAccessToken,
    TokenConfigurationError,
    get_user_id_from_token,
)
from app.models.user_model import User


# ===================================
# DATABASE DEPENDENCY
# ===================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        user_id = get_user_id_from_token(credentials.credentials)
    except InvalidAccessToken:
        raise unauthorized from None
    except TokenConfigurationError:
        raise HTTPException(
            status_code=503,
            detail="Authentication is unavailable.",
        ) from None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_phase2_tenant_scoping() -> None:
    """Fail closed for legacy data endpoints without business ownership columns."""
    raise HTTPException(
        status_code=503,
        detail="This endpoint is unavailable until business data is tenant-scoped.",
    )
