from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import (
    Permission,
    get_business_context,
    require_permission,
)
from app.core.dependencies import get_db
from app.models.business_membership_model import BusinessMembership, MembershipRole
from app.models.settings_model import SettingsModel
from app.services.business_settings import (
    LegacySettingsNotBackfilled,
    get_or_create_business_settings,
)
from app.schemas.settings_schema import (
    SettingsIntegrationUpdate,
    SettingsRead,
    SettingsUpdate,
    SettingsUpdateResponse,
)


router = APIRouter(prefix="/settings", tags=["Settings"])


def _safe_settings(settings_row: SettingsModel) -> SettingsRead:
    fields = set(SettingsRead.model_fields) - {"shopify_connected", "meta_connected"}
    values = {field: getattr(settings_row, field) for field in fields}
    values["shopify_connected"] = bool(settings_row.shopify_access_token)
    values["meta_connected"] = bool(settings_row.meta_access_token)
    return SettingsRead.model_validate(values)


def _require_single_business_permission(
    membership: BusinessMembership,
    permission: Permission,
    *,
    owner_only: bool = False,
) -> None:
    require_permission(membership, permission)
    if owner_only and MembershipRole(membership.role) != MembershipRole.OWNER:
        raise HTTPException(status_code=403, detail="Owner permission is required.")


@router.get("/", response_model=SettingsRead)
def get_settings(
    membership: BusinessMembership = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    _require_single_business_permission(membership, Permission.SETTINGS_READ)
    settings_row = db.query(SettingsModel).first()
    if settings_row is None:
        raise HTTPException(status_code=404, detail="Settings are not configured.")
    return _safe_settings(settings_row)


@router.post("/", response_model=SettingsUpdateResponse)
def update_settings(
    data: SettingsUpdate,
    membership: BusinessMembership = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    _require_single_business_permission(membership, Permission.SETTINGS_WRITE)
    try:
        settings_row = get_or_create_business_settings(db)
    except LegacySettingsNotBackfilled as error:
        raise HTTPException(status_code=409, detail=str(error)) from None

    for field in data.model_fields_set:
        setattr(settings_row, field, getattr(data, field))
    try:
        db.commit()
        db.refresh(settings_row)
    except Exception:
        db.rollback()
        raise
    return SettingsUpdateResponse(
        message="Settings updated successfully.",
        settings=_safe_settings(settings_row),
    )


@router.put("/integrations", response_model=SettingsUpdateResponse)
def update_integration_credentials(
    data: SettingsIntegrationUpdate,
    membership: BusinessMembership = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    _require_single_business_permission(
        membership,
        Permission.INTEGRATIONS_MANAGE,
        owner_only=True,
    )
    try:
        settings_row = get_or_create_business_settings(db)
    except LegacySettingsNotBackfilled as error:
        raise HTTPException(status_code=409, detail=str(error)) from None

    fields = data.model_fields_set
    for field in ("shopify_store_url", "meta_account_id"):
        if field in fields:
            setattr(settings_row, field, getattr(data, field))
    for field in ("shopify_access_token", "meta_access_token"):
        if field in fields:
            secret = getattr(data, field)
            setattr(settings_row, field, secret.get_secret_value())
    if data.clear_shopify_access_token:
        settings_row.shopify_access_token = None
    if data.clear_meta_access_token:
        settings_row.meta_access_token = None

    try:
        db.commit()
        db.refresh(settings_row)
    except Exception:
        db.rollback()
        raise
    return SettingsUpdateResponse(
        message="Integration settings updated successfully.",
        settings=_safe_settings(settings_row),
    )
