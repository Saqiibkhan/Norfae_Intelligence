from fastapi import APIRouter
from fastapi import Depends

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.services.product_intelligence_service import (
    ProductIntelligenceService
)

# ===================================
# ROUTER
# ===================================

router = APIRouter(

    tags=["Product Intelligence"]
)

# ===================================
# PRODUCT INTELLIGENCE ENDPOINT
# ===================================

@router.get(
    "/products/intelligence"
)
def get_product_intelligence(
    db: Session = Depends(get_db)
):

    intelligence = (
        ProductIntelligenceService
        .get_product_intelligence(
            db
        )
    )

    return {

        "success": True,

        "products": intelligence
    }