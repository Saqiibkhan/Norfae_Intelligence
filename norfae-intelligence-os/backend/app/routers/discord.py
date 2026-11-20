from fastapi import APIRouter, Depends

from pydantic import BaseModel

from app.services.discord_service import (
    DiscordOrderService
)
from app.core.authorization import get_business_context
from app.models.business_membership_model import BusinessMembership

router = APIRouter(

    prefix="/discord-orders",

    tags=["Discord Orders"]
)

# ===================================
# REQUEST MODEL
# ===================================

class DiscordStatusUpdate(

    BaseModel
):

    internal_order_id: str

    status: str

# ===================================
# UPDATE STATUS
# ===================================

@router.post(
    "/update-status"
)
def update_status(

    data: DiscordStatusUpdate,
    membership: BusinessMembership = Depends(get_business_context),
):

    return (

        DiscordOrderService
        .update_order_status(

            internal_order_id=(
                data.internal_order_id
            ),

            status=data.status,
            business_id=membership.business_id,
        )
    )
