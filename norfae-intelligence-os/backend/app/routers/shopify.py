from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.authorization import get_business_context
from app.core.dependencies import get_db
from app.core.dependencies import get_current_user
from app.models.business_membership_model import BusinessMembership

from app.services.shopify_service import (
    ShopifyService
)
from app.services.shopify_sync_service import ShopifySyncError, ShopifySyncService
from app.models.user_model import User
from app.schemas.shopify_schema import ShopifyFullSyncResponse, ShopifyStatusResponse, ShopifySyncRunResponse

router = APIRouter(
    prefix="/shopify",
    tags=["Shopify"]
)


@router.get("/status", response_model=ShopifyStatusResponse)
def shopify_status(
    membership: BusinessMembership = Depends(get_business_context),
    db: Session = Depends(get_db),
):

    return (
        ShopifyService
        .service_status(db, membership.business_id)
    )


def _sync_result(call):
    try:
        result = call()
    except ShopifySyncError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail={"code": error.category, "message": error.summary},
        ) from None
    if result["status"] == "failed":
        category = result.get("error_category") or "sync_failed"
        status_code = 409 if category in {"sync_in_progress", "store_changed", "configuration_missing", "configuration_invalid"} else 502
        raise HTTPException(
            status_code=status_code,
            detail={"code": category,
                    "message": result.get("message") or "Shopify synchronization failed."},
        )
    return result


@router.post("/sync/products", response_model=ShopifySyncRunResponse)
def sync_products(
    membership: BusinessMembership = Depends(get_business_context),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _sync_result(lambda: ShopifySyncService.sync_products(db, membership.business_id, current_user.id))


@router.post("/sync/orders", response_model=ShopifySyncRunResponse)
def sync_orders(
    membership: BusinessMembership = Depends(get_business_context),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _sync_result(lambda: ShopifySyncService.sync_orders(db, membership.business_id, current_user.id))


@router.post("/sync", response_model=ShopifyFullSyncResponse)
def sync_all(
    membership: BusinessMembership = Depends(get_business_context),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = _sync_result(lambda: ShopifySyncService.sync_all(db, membership.business_id, current_user.id))
    if result["status"] == "failed":
        error_category = result["products"].get("error_category") or result["orders"].get("error_category") or "sync_failed"
        status_code = 409 if error_category in {"sync_in_progress", "store_changed", "configuration_missing", "configuration_invalid"} else 502
        raise HTTPException(status_code=status_code, detail={"code": error_category, "message": "Shopify synchronization failed; see sync history."})
    return result


@router.get("/sync/history", response_model=list[ShopifySyncRunResponse])
def sync_history(
    membership: BusinessMembership = Depends(get_business_context),
    db: Session = Depends(get_db),
):
    return ShopifySyncService.history(db, membership.business_id)
