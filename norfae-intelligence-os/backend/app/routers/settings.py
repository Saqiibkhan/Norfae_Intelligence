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
from app.models import (
    MetaSyncRun, MetaSyncState, ShopifySyncRun, ShopifySyncState,
)
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
from app.utils.shopify_url import normalize_shopify_store_url


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
    meta_configuration_changed = bool(
        fields.intersection({"meta_account_id", "meta_access_token"})
        or data.clear_meta_access_token
    )
    if meta_configuration_changed:
        state = db.query(MetaSyncState).filter(
            MetaSyncState.business_id == membership.business_id
        ).with_for_update().first()
        if state is None:
            state = MetaSyncState(business_id=membership.business_id)
            db.add(state)
            db.flush()
    if "meta_account_id" in fields:
        current_account = settings_row.meta_account_id
        if isinstance(current_account, str) and current_account.startswith("act_"):
            current_account = current_account[4:]
        requested_account = data.meta_account_id
        if current_account != requested_account:
            if state.running_since:
                raise HTTPException(status_code=409, detail="Cannot change the selected Meta ad account while synchronization is running.")
            successful = db.query(MetaSyncRun.id).filter(
                MetaSyncRun.business_id == membership.business_id,
                MetaSyncRun.status.in_(("completed", "partially_completed")),
            ).first()
            if successful:
                raise HTTPException(status_code=409, detail="This business has synchronized a Meta ad account. A reviewed data reset is required before changing accounts.")
    if "shopify_store_url" in fields:
        state = db.query(ShopifySyncState).filter(
            ShopifySyncState.business_id == membership.business_id
        ).with_for_update().first()
        requested_domain = normalize_shopify_store_url(data.shopify_store_url) if data.shopify_store_url else None
        current_domain = normalize_shopify_store_url(settings_row.shopify_store_url) if settings_row.shopify_store_url else None
        if requested_domain != current_domain and state:
            if state.products_running_since or state.orders_running_since:
                raise HTTPException(status_code=409, detail="Cannot change Shopify stores while synchronization is running.")
            successful = db.query(ShopifySyncRun.id).filter(
                ShopifySyncRun.business_id == membership.business_id,
                ShopifySyncRun.status.in_(("completed", "partially_completed")),
            ).first()
            if successful:
                raise HTTPException(status_code=409, detail="This business has synchronized a Shopify store. A reviewed data reset is required before changing stores.")
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
