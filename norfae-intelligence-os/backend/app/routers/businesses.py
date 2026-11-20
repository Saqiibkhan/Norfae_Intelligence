from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import (
    Permission,
    get_active_business_membership,
    has_permission,
    require_business_permission,
)
from app.core.dependencies import get_current_user, get_db
from app.models.business_membership_model import BusinessMembership, MembershipRole
from app.models.business_model import Business
from app.models.user_model import User
from app.schemas.auth_schema import (
    AccessibleBusinessResponse,
    BusinessCreate,
    BusinessMembershipResponse,
    BusinessResponse,
    BusinessUpdate,
    MembershipCreate,
    MembershipUpdate,
)


router = APIRouter(prefix="/businesses", tags=["Businesses"])


def _membership_response(membership: BusinessMembership) -> BusinessMembershipResponse:
    return BusinessMembershipResponse(
        user_id=membership.user.id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        is_active=membership.is_active,
        created_at=membership.created_at,
    )


def _check_actor_can_manage_target(
    actor: BusinessMembership,
    target: BusinessMembership,
) -> None:
    actor_role = MembershipRole(actor.role)
    target_role = MembershipRole(target.role)
    if target_role == MembershipRole.OWNER or target.business.owner_id == target.user_id:
        raise HTTPException(
            status_code=409,
            detail="The business owner cannot be changed through membership management.",
        )
    if actor_role == MembershipRole.ADMIN and target_role == MembershipRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Admins cannot manage other admins.",
        )


@router.get("", response_model=list[AccessibleBusinessResponse])
def list_businesses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(BusinessMembership)
        .join(Business, Business.id == BusinessMembership.business_id)
        .filter(
            BusinessMembership.user_id == current_user.id,
            BusinessMembership.is_active.is_(True),
            Business.is_active.is_(True),
        )
        .order_by(Business.id)
        .all()
    )
    return [
        AccessibleBusinessResponse(
            **BusinessResponse.model_validate(membership.business).model_dump(),
            role=membership.role,
        )
        for membership in memberships
    ]


@router.post("", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
def create_business(
    payload: BusinessCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    business = Business(name=payload.name, owner=current_user)
    membership = BusinessMembership(
        user=current_user,
        business=business,
        role=MembershipRole.OWNER,
        is_active=True,
    )
    db.add_all([business, membership])
    try:
        db.flush()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return business


@router.get("/{business_id}", response_model=AccessibleBusinessResponse)
def get_business(
    membership: BusinessMembership = Depends(
        require_business_permission(Permission.BUSINESS_READ)
    ),
):
    return AccessibleBusinessResponse(
        **BusinessResponse.model_validate(membership.business).model_dump(),
        role=membership.role,
    )


@router.patch("/{business_id}", response_model=BusinessResponse)
def update_business(
    payload: BusinessUpdate,
    membership: BusinessMembership = Depends(
        require_business_permission(Permission.BUSINESS_UPDATE)
    ),
    db: Session = Depends(get_db),
):
    membership.business.name = payload.name
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    return membership.business


@router.get(
    "/{business_id}/memberships",
    response_model=list[BusinessMembershipResponse],
)
def list_memberships(
    membership: BusinessMembership = Depends(
        require_business_permission(Permission.MEMBERS_READ)
    ),
    db: Session = Depends(get_db),
):
    memberships = (
        db.query(BusinessMembership)
        .filter(BusinessMembership.business_id == membership.business_id)
        .order_by(BusinessMembership.id)
        .all()
    )
    return [_membership_response(item) for item in memberships]


@router.post(
    "/{business_id}/memberships",
    response_model=BusinessMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_membership(
    payload: MembershipCreate,
    actor: BusinessMembership = Depends(
        require_business_permission(Permission.MEMBERS_MANAGE)
    ),
    db: Session = Depends(get_db),
):
    requested_role = MembershipRole(payload.role)
    actor_role = MembershipRole(actor.role)
    if requested_role == MembershipRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail="Owner membership is assigned only during business creation.",
        )
    if actor_role == MembershipRole.ADMIN and requested_role == MembershipRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only owners can add admins.")

    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=404,
            detail="An active account with this email must register first.",
        )

    existing = (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == actor.business_id,
            BusinessMembership.user_id == user.id,
        )
        .first()
    )
    if existing is not None:
        if existing.is_active:
            raise HTTPException(status_code=409, detail="Membership already exists.")
        if (
            MembershipRole(existing.role) == MembershipRole.OWNER
            or actor.business.owner_id == user.id
        ):
            raise HTTPException(status_code=409, detail="Owner membership is inconsistent.")
        if actor_role == MembershipRole.ADMIN and MembershipRole(existing.role) == MembershipRole.ADMIN:
            raise HTTPException(status_code=403, detail="Admins cannot manage other admins.")
        existing.role = requested_role
        existing.is_active = True
        result = existing
    else:
        result = BusinessMembership(
            user=user,
            business=actor.business,
            role=requested_role,
            is_active=True,
        )
        db.add(result)

    try:
        db.commit()
        db.refresh(result)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Membership already exists.") from None
    return _membership_response(result)


@router.patch(
    "/{business_id}/memberships/{user_id}",
    response_model=BusinessMembershipResponse,
)
def update_membership(
    payload: MembershipUpdate,
    user_id: int,
    actor: BusinessMembership = Depends(
        require_business_permission(Permission.MEMBERS_MANAGE)
    ),
    db: Session = Depends(get_db),
):
    target = (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == actor.business_id,
            BusinessMembership.user_id == user_id,
        )
        .first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Membership not found.")
    _check_actor_can_manage_target(actor, target)
    actor_role = MembershipRole(actor.role)

    if "role" in payload.model_fields_set:
        requested_role = MembershipRole(payload.role)
        if requested_role == MembershipRole.OWNER:
            raise HTTPException(status_code=403, detail="Ownership transfer is not available.")
        if actor_role == MembershipRole.ADMIN and requested_role == MembershipRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only owners can assign admins.")
        target.role = requested_role
    if "is_active" in payload.model_fields_set:
        target.is_active = payload.is_active

    try:
        db.commit()
        db.refresh(target)
    except Exception:
        db.rollback()
        raise
    return _membership_response(target)


@router.delete("/{business_id}/memberships/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_membership(
    user_id: int,
    actor: BusinessMembership = Depends(
        require_business_permission(Permission.MEMBERS_MANAGE)
    ),
    db: Session = Depends(get_db),
):
    target = (
        db.query(BusinessMembership)
        .filter(
            BusinessMembership.business_id == actor.business_id,
            BusinessMembership.user_id == user_id,
        )
        .first()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Membership not found.")
    _check_actor_can_manage_target(actor, target)
    db.delete(target)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
