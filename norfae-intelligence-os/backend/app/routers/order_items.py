from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.order_item_model import OrderItem

from app.models.order_model import Order

from app.models.inventory_product_model import InventoryProduct

from app.services.order_recalculation_service import OrderRecalculationService

from app.services.product_normalization_service import ProductNormalizationService

# ===================================
# ROUTER
# ===================================

router = APIRouter(prefix="/order-items", tags=["Order Items"])


# ===================================
# REQUEST MODEL
# ===================================


class OrderItemUpdateRequest(BaseModel):

    sku: str | None = None

    quantity: int | None = None

    size: str | None = None


# ===================================
# UPDATE ORDER ITEM
# ===================================


@router.put("/{item_id}")
def update_order_item(
    item_id: int, payload: OrderItemUpdateRequest, db: Session = Depends(get_db)
):

    # ===================================
    # FIND ITEM
    # ===================================

    order_item = db.query(OrderItem).filter(OrderItem.id == item_id).first()

    if not order_item:

        raise HTTPException(status_code=404, detail="Order item not found")

    # ===================================
    # UPDATE SKU
    # ===================================

    if payload.sku:

        inventory_product = (
            db.query(InventoryProduct)
            .filter(InventoryProduct.sku == payload.sku)
            .first()
        )

        if not inventory_product:

            raise HTTPException(status_code=404, detail="Inventory product not found")

        order_item.inventory_product_id = inventory_product.id

        order_item.sku = inventory_product.sku

        order_item.product_name = inventory_product.product_name

        order_item.normalized_name = ProductNormalizationService.normalize_product_name(
            inventory_product.product_name
        )

        order_item.size = inventory_product.size

        order_item.unit_cost = float(inventory_product.product_cost or 0)

        order_item.unit_price = float(inventory_product.selling_price or 0)

        order_item.total_cost = order_item.unit_cost * order_item.quantity

        order_item.total_price = order_item.unit_price * order_item.quantity

    # ===================================
    # UPDATE QUANTITY
    # ===================================

    if payload.quantity:

        order_item.quantity = payload.quantity

        order_item.total_cost = order_item.unit_cost * order_item.quantity

        order_item.total_price = order_item.unit_price * order_item.quantity

    # ===================================
    # UPDATE SIZE
    # ===================================

    if payload.size:

        order_item.size = payload.size

    # ===================================
    # RECALCULATE ORDER
    # ===================================

    order = db.query(Order).filter(Order.id == order_item.order_id).first()

    if order:

        OrderRecalculationService.recalculate_order(db=db, order=order)

    # ===================================
    # SAVE
    # ===================================

    db.commit()

    db.refresh(order_item)

    return {"message": "Order item updated successfully", "order_item": order_item}
