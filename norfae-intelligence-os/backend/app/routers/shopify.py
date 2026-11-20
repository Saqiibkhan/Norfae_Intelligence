from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.authorization import get_business_context
from app.core.dependencies import get_db
from app.models.business_membership_model import BusinessMembership

from app.services.shopify_service import (
    ShopifyService
)

router = APIRouter(
    prefix="/shopify",
    tags=["Shopify"]
)


@router.get("/status")
def shopify_status(
    membership: BusinessMembership = Depends(get_business_context),
    db: Session = Depends(get_db),
):

    return (
        ShopifyService
        .service_status(db, membership.business_id)
    )
