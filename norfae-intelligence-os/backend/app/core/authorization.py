from enum import Enum

from collections.abc import AsyncIterator, Iterator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.dependencies import get_current_user, get_db
from app.core.tenant_context import reset_current_business_id, set_current_business_id
from app.models.business_membership_model import BusinessMembership, MembershipRole
from app.models.business_model import Business
from app.models.user_model import User


class Permission(str, Enum):
    BUSINESS_READ = "business:read"
    BUSINESS_UPDATE = "business:update"
    ANALYTICS_READ = "analytics:read"
    MEMBERS_READ = "members:read"
    MEMBERS_MANAGE = "members:manage"
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    INTEGRATIONS_MANAGE = "integrations:manage"


ROLE_PERMISSIONS: dict[MembershipRole, frozenset[Permission]] = {
    MembershipRole.OWNER: frozenset(Permission),
    MembershipRole.ADMIN: frozenset(
        {
            Permission.BUSINESS_READ,
            Permission.BUSINESS_UPDATE,
            Permission.ANALYTICS_READ,
            Permission.MEMBERS_READ,
            Permission.MEMBERS_MANAGE,
            Permission.SETTINGS_READ,
            Permission.SETTINGS_WRITE,
        }
    ),
    MembershipRole.ANALYST: frozenset(
        {Permission.BUSINESS_READ, Permission.ANALYTICS_READ}
    ),
    MembershipRole.VIEWER: frozenset(
        {Permission.BUSINESS_READ, Permission.ANALYTICS_READ}
    ),
}


def has_permission(role: MembershipRole | str, permission: Permission) -> bool:
    try:
        normalized_role = MembershipRole(role)
    except (TypeError, ValueError):
        return False
    return permission in ROLE_PERMISSIONS[normalized_role]


def require_permission(
    membership: BusinessMembership, permission: Permission
) -> None:
    if not has_permission(membership.role, permission):
        raise HTTPException(status_code=403, detail="Insufficient business permissions.")


def get_active_business_membership(
    business_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessMembership:
    membership = (
        db.query(BusinessMembership)
        .join(Business, Business.id == BusinessMembership.business_id)
        .filter(
            BusinessMembership.business_id == business_id,
            BusinessMembership.user_id == current_user.id,
            BusinessMembership.is_active.is_(True),
            Business.is_active.is_(True),
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Business not found.")

    is_owner_id = membership.business.owner_id == current_user.id
    is_owner_role = MembershipRole(membership.role) == MembershipRole.OWNER
    if is_owner_id != is_owner_role:
        raise HTTPException(
            status_code=403,
            detail="Business ownership membership is inconsistent.",
        )
    return membership


async def get_business_context(
    request: Request,
    x_business_id: int = Header(..., alias="X-Business-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsyncIterator[BusinessMembership]:
    """Verify selected business access and scope all ORM work for this request."""
    def load_membership():
        return (
            db.query(BusinessMembership)
            .join(Business, Business.id == BusinessMembership.business_id)
            .filter(
                BusinessMembership.business_id == x_business_id,
                BusinessMembership.user_id == current_user.id,
                BusinessMembership.is_active.is_(True),
                Business.is_active.is_(True),
            )
            .first()
        )

    membership = await run_in_threadpool(load_membership)
    if membership is None:
        raise HTTPException(status_code=404, detail="Business not found.")
    is_owner = membership.business.owner_id == current_user.id
    has_owner_role = MembershipRole(membership.role) == MembershipRole.OWNER
    if is_owner != has_owner_role:
        raise HTTPException(status_code=403, detail="Business ownership membership is inconsistent.")

    path = request.url.path.lower()
    integration_write = request.method.upper() not in {"GET", "HEAD", "OPTIONS"} and (
        path.startswith(("/meta-ads", "/shopify", "/discord"))
        or "/sync" in path
    )
    required_permission = (
        Permission.INTEGRATIONS_MANAGE
        if integration_write
        else Permission.ANALYTICS_READ
        if request.method.upper() in {"GET", "HEAD", "OPTIONS"}
        else Permission.BUSINESS_UPDATE
    )
    require_permission(membership, required_permission)

    context_token = set_current_business_id(x_business_id)
    try:
        yield membership
    finally:
        reset_current_business_id(context_token)


def require_business_permission(permission: Permission):
    def dependency(
        membership: BusinessMembership = Depends(get_active_business_membership),
    ) -> BusinessMembership:
        require_permission(membership, permission)
        return membership

    return dependency


def get_single_business_settings_membership(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BusinessMembership:
    businesses = db.query(Business).order_by(Business.id).limit(2).all()
    if len(businesses) != 1 or not businesses[0].is_active:
        raise HTTPException(
            status_code=409,
            detail="Shared settings are disabled until settings are business-scoped.",
        )
    membership = (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == businesses[0].id,
            BusinessMembership.user_id == current_user.id,
            BusinessMembership.is_active.is_(True),
        )
        .first()
    )
    if membership is None:
        raise HTTPException(status_code=403, detail="Active business membership required.")
    if (businesses[0].owner_id == current_user.id) != (
        MembershipRole(membership.role) == MembershipRole.OWNER
    ):
        raise HTTPException(
            status_code=403,
            detail="Business ownership membership is inconsistent.",
        )
    return membership
