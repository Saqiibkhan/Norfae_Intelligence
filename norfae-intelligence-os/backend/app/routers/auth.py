from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.security import SecurityManager
from app.core.tokens import TokenConfigurationError, create_access_token
from app.models.business_membership_model import BusinessMembership, MembershipRole
from app.models.business_model import Business
from app.models.user_model import User
from app.schemas.auth_schema import (
    AuthenticatedUserResponse,
    AuthenticationResponse,
    BusinessResponse,
    LoginRequest,
    RegistrationRequest,
    TokenResponse,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


def _authentication_response(user: User, business: Business | None = None):
    return AuthenticationResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=AuthenticatedUserResponse.model_validate(user),
        business=(BusinessResponse.model_validate(business) if business else None),
    )


def _login_business(db: Session, user: User) -> Business | None:
    """Return one active, internally consistent membership for login display.

    This is informational only. Protected requests still require the caller to
    select a business through X-Business-ID, which is checked independently.
    """
    memberships = (
        db.query(BusinessMembership, Business)
        .join(Business, Business.id == BusinessMembership.business_id)
        .filter(
            BusinessMembership.user_id == user.id,
            BusinessMembership.is_active.is_(True),
            Business.is_active.is_(True),
        )
        .order_by(Business.id)
        .all()
    )
    for membership, business in memberships:
        is_owner = business.owner_id == user.id
        has_owner_role = MembershipRole(membership.role) == MembershipRole.OWNER
        if is_owner == has_owner_role:
            return business
    return None


@router.post(
    "/register",
    response_model=AuthenticationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: RegistrationRequest,
    db: Session = Depends(get_db),
) -> AuthenticationResponse:
    password = payload.password.get_secret_value()
    password_hash = SecurityManager.hash_password(password)
    user = User(
        email=payload.email,
        password_hash=password_hash,
        full_name=payload.full_name,
    )
    db.add(user)

    try:
        db.flush()
        business = Business(name=payload.business_name, owner=user)
        db.add(business)
        db.flush()
        membership = BusinessMembership(
            user=user,
            business=business,
            role=MembershipRole.OWNER,
            is_active=True,
        )
        db.add(membership)
        db.flush()
        response = _authentication_response(user, business)
        db.commit()
        return response
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists or registration conflicts.",
        ) from None
    except TokenConfigurationError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is unavailable.",
        ) from None
    except Exception:
        db.rollback()
        raise


@router.post("/login", response_model=AuthenticationResponse)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> AuthenticationResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    password = payload.password.get_secret_value()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not SecurityManager.verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    try:
        return _authentication_response(user, _login_business(db, user))
    except TokenConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is unavailable.",
        ) from None


@router.get("/me", response_model=AuthenticatedUserResponse)
def current_user_profile(
    current_user: User = Depends(get_current_user),
) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse.model_validate(current_user)
