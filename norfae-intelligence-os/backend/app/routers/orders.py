from fastapi import APIRouter, Depends, Query, HTTPException

from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel

from app.core.database import SessionLocal, get_db

from app.models.product_model import Product

from app.models.order_model import Order

from app.models.order_item_model import OrderItem

from app.services.order_analysis_service import OrderAnalysisService

from app.services.order_intelligence_service import OrderIntelligenceService

from app.services.delivery_cost_service import DeliveryCostService

from app.services.order_recalculation_service import OrderRecalculationService
from app.services.business_settings import (
    LegacySettingsNotBackfilled,
    get_or_create_business_settings,
)
from sqlalchemy.orm import joinedload

from app.services.product_normalization_service import ProductNormalizationService
from app.services.city_province_service import CityProvinceService

# ===================================
# ROUTER
# ===================================

router = APIRouter(prefix="/orders", tags=["Orders"])

# ===================================
# REQUEST MODEL
# ===================================


class OrderCreate(BaseModel):

    customer_name: str

    customer_phone: str

    city: str

    address: str

    sku: str

    quantity: int

    marketing_cost: float = 0

    other_expense: float = 0

    source: str


class OrderLocationUpdateRequest(BaseModel):

    city: str

    province: str | None = None


# ===================================
# GET ORDERS
# ===================================


@router.get("/")
def get_orders(
    filter_type: str = Query(default="today"),
    start_date: str = None,
    end_date: str = None,
):
    db = SessionLocal()

    # ===================================
    # BASE QUERY
    # ===================================

    query = db.query(Order).options(joinedload(Order.items))

    # ===================================
    # Pakistan Time NOW
    # ===================================

    pkt_now = datetime.utcnow() + timedelta(hours=5)

    # ===================================
    # ALL ORDERS
    # ===================================

    if filter_type == "all":

        pass

    # ===================================
    # TODAY
    # ===================================

    if filter_type == "today":

        start = pkt_now.replace(hour=0, minute=0, second=0, microsecond=0)

        end = start + timedelta(days=1)

        query = query.filter(
            Order.discord_created_at >= start, Order.discord_created_at < end
        )

    # ===================================
    # YESTERDAY
    # ===================================

    elif filter_type == "yesterday":

        end = pkt_now.replace(hour=0, minute=0, second=0, microsecond=0)

        start = end - timedelta(days=1)

        query = query.filter(
            Order.discord_created_at >= start, Order.discord_created_at < end
        )

    # ===================================
    # THIS WEEK
    # ===================================

    elif filter_type == "week":

        start = pkt_now - timedelta(days=pkt_now.weekday())

        start = start.replace(hour=0, minute=0, second=0, microsecond=0)

        query = query.filter(Order.discord_created_at >= start)

    # ===================================
    # THIS MONTH
    # ===================================

    elif filter_type == "month":

        start = pkt_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        query = query.filter(Order.discord_created_at >= start)
    # ===================================
    # CUSTOM RANGE
    # ===================================

    elif filter_type == "custom" and start_date and end_date:

        start = datetime.strptime(start_date, "%Y-%m-%d")

        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        query = query.filter(
            Order.discord_created_at >= start, Order.discord_created_at < end
        )

    # ===================================
    # DEFAULT ORDERING
    # ===================================

    orders = query.order_by(
        Order.confirmed_order_date.is_(None),
        Order.confirmed_order_date.desc(),
        Order.created_at.desc(),
    ).all()

    results = []

    for order in orders:

        # ===============================
        # RECALCULATE LIVE INTELLIGENCE
        # ===============================

        order.total_cost = OrderIntelligenceService.calculate_total_cost(order)

        order.net_profit = OrderIntelligenceService.calculate_net_profit(order)

        order.profit_margin = OrderIntelligenceService.calculate_profit_margin(order)

        # ===============================
        # ANALYSIS
        # ===============================

        analysis = OrderAnalysisService.analyze_order_status(order.status)

        # ===============================
        # DELIVERY FILTER
        # ===============================

        delivery_cost = order.delivery_cost

        if order.status and order.status.upper() == "CANCELLED":

            delivery_cost = 0

        # ===============================
        # RESPONSE
        # ===============================

        results.append(
            {
                "id": order.id,
                "internal_order_id": order.internal_order_id,
                "customer_name": order.customer_name,
                "customer_phone": order.customer_phone,
                "city": order.city,
                "province": order.province,
                "address": order.address,
                "product_name": order.product_name,
                "sku": order.sku,
                "size": order.size,
                "quantity": order.quantity,
                # ===================================
                # SINGLE PRODUCT ITEM ID
                # ===================================
                "order_item_id": order.items[0].id if order.items else None,
                # ===================================
                # MULTI PRODUCTS
                # ===================================
                "products": [
                    {
                        "id": item.id,
                        "name": item.product_name,
                        "sku": item.sku,
                        "size": item.size,
                        "quantity": item.quantity,
                        "unit_cost": item.unit_cost,
                        "total_cost": item.total_cost,
                        "unit_price": item.unit_price,
                        "total_price": item.total_price,
                    }
                    for item in order.items
                ],
                "weight_kg": order.weight_kg,
                "selling_price": order.selling_price,
                "product_cost": order.product_cost,
                "delivery_cost": delivery_cost,
                "packaging_cost": order.packaging_cost,
                "marketing_cost": order.marketing_cost,
                "other_expense": order.other_expense,
                "total_cost": round(order.total_cost, 2),
                "net_profit": round(order.net_profit, 2),
                "profit_margin": round(order.profit_margin, 2),
                "source": order.source,
                "status": order.status,
                "health_score": analysis["health_score"],
                "category": analysis["category"],
                "discord_created_at": order.discord_created_at,
                "confirmed_order_date": order.confirmed_order_date,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
            }
        )
    db.close()

    return results


# ===================================
# CREATE ORDER
# ===================================


@router.post("/")
def create_order(order: OrderCreate):

    db = SessionLocal()

    # ===================================
    # FIND PRODUCT
    # ===================================

    product = db.query(Product).filter(Product.sku == order.sku).first()

    if not product:

        db.close()

        return {"error": "Product not found"}

    # ===================================
    # LOAD SETTINGS
    # ===================================

    try:
        settings = get_or_create_business_settings(db)
    except LegacySettingsNotBackfilled as error:
        db.close()
        raise HTTPException(status_code=409, detail=str(error)) from None

    # ===================================
    # PRODUCT INTELLIGENCE
    # ===================================

    weight_kg = product.weight_kg * order.quantity

    selling_price = product.selling_price * order.quantity

    product_cost = product.buying_price * order.quantity

    # ===================================
    # DELIVERY INTELLIGENCE
    # ===================================

    province = CityProvinceService.get_province(order.city)

    delivery_data = DeliveryCostService.calculate_delivery_cost(
        city=order.city,
        weight_kg=weight_kg,
        order_amount=selling_price,
        settings=settings,
    )

    # ===================================
    # CREATE ORDER
    # ===================================

    new_order = Order(
        internal_order_id=(f"NRF-" f"{order.customer_phone[-4:]}"),
        customer_name=order.customer_name,
        customer_phone=order.customer_phone,
        city=order.city,
        province=province,
        address=order.address,
        product_name=product.name,
        sku=product.sku,
        size=product.size,
        quantity=order.quantity,
        weight_kg=weight_kg,
        selling_price=selling_price,
        product_cost=product_cost,
        delivery_cost=(delivery_data["delivery_cost"]),
        packaging_cost=(settings.packaging_cost),
        marketing_cost=order.marketing_cost,
        other_expense=order.other_expense,
        source=order.source,
        status="PENDING",
    )

    # ===================================
    # CALCULATIONS
    # ===================================

    new_order.total_cost = OrderIntelligenceService.calculate_total_cost(new_order)

    new_order.net_profit = OrderIntelligenceService.calculate_net_profit(new_order)

    new_order.profit_margin = OrderIntelligenceService.calculate_profit_margin(
        new_order
    )

    # ===================================
    # PRODUCT ANALYTICS
    # ===================================

    product.total_orders += order.quantity

    # ===================================
    # SAVE
    # ===================================

    db.add(new_order)

    db.commit()

    db.refresh(new_order)

    # ===================================
    # CREATE ORDER ITEM
    # ===================================

    order_item = OrderItem(
        order_id=new_order.id,
        product_name=product.name,
        normalized_name=(
            ProductNormalizationService.normalize_product_name(product.name)
            if product.name
            else "unknown product"
        ),
        sku=product.sku,
        variant=product.size,
        size=product.size,
        quantity=order.quantity,
        unit_price=float(product.selling_price or 0),
        total_price=float(selling_price or 0),
        unit_cost=float(product.buying_price or 0),
        total_cost=float(product_cost or 0),
        profit=float(new_order.net_profit or 0),
    )

    db.add(order_item)

    db.commit()

    db.close()

    return {
        "message": "Order created successfully",
        "delivery_breakdown": delivery_data,
        "order": new_order,
    }


# ===================================
# RECALCULATE ALL ORDERS
# ===================================


@router.post("/recalculate")
def recalculate_orders(db: Session = Depends(get_db)):

    return OrderRecalculationService.recalculate_all_orders(db)


@router.put("/{order_id}/location")
def update_order_location(
    order_id: int,
    payload: OrderLocationUpdateRequest,
    db: Session = Depends(get_db),
):

    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:

        return {"success": False, "message": "Order not found"}

    order.city = payload.city

    if payload.province:

        order.province = payload.province

    else:

        order.province = CityProvinceService.get_province(payload.city)

    OrderRecalculationService.recalculate_order(db=db, order=order)

    db.commit()

    db.refresh(order)

    return {"success": True, "message": "Location updated"}
