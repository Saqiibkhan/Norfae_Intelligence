from app.core.database import SessionLocal

from app.models.product_model import Product

from app.models.order_model import Order

from app.models.order_item_model import OrderItem

from app.services.delivery_cost_service import DeliveryCostService

from app.services.order_intelligence_service import OrderIntelligenceService

from app.services.product_normalization_service import ProductNormalizationService

from app.services.city_province_service import CityProvinceService
from app.services.business_settings import (
    LegacySettingsNotBackfilled,
    get_or_create_business_settings,
)


class OrderCreationService:

    # ===================================
    # CREATE ORDER
    # ===================================

    @staticmethod
    def create_order(
        customer_name: str,
        customer_phone: str,
        city: str,
        address: str,
        sku: str,
        quantity: int,
        source: str,
        marketing_cost: float = 0,
        other_expense: float = 0,
    ):

        db = SessionLocal()

        # ===================================
        # FIND PRODUCT
        # ===================================

        product = db.query(Product).filter(Product.sku == sku).first()

        if not product:

            db.close()

            return {"success": False, "message": "Product not found"}

        # ===================================
        # SETTINGS
        # ===================================

        try:
            settings = get_or_create_business_settings(db)
        except LegacySettingsNotBackfilled as error:
            db.close()
            return {"success": False, "message": str(error)}

        # ===================================
        # PRODUCT DATA
        # ===================================

        weight_kg = product.weight_kg * quantity

        selling_price = product.selling_price * quantity

        product_cost = product.buying_price * quantity

        # ===================================
        # DELIVERY COST
        # ===================================

        delivery_data = DeliveryCostService.calculate_delivery_cost(
            city=city,
            weight_kg=weight_kg,
            order_amount=selling_price,
            settings=settings,
        )

        delivery_cost = delivery_data["delivery_cost"]

        # ===================================
        # CREATE ORDER
        # ===================================

        province = CityProvinceService.get_province(city)

        normalized_city = city

        province = CityProvinceService.get_province(normalized_city)

        print("==============")
        print("CITY:", normalized_city)
        print("PROVINCE:", province)
        print("==============")

        order = Order(
            internal_order_id=(f"NRF-" f"{customer_phone[-4:]}"),
            customer_name=customer_name,
            customer_phone=customer_phone,
            city=city,
            province=province,
            address=address,
            product_name=product.name,
            sku=product.sku,
            size=product.size,
            quantity=quantity,
            weight_kg=weight_kg,
            selling_price=selling_price,
            product_cost=product_cost,
            delivery_cost=delivery_cost,
            packaging_cost=(settings.packaging_cost),
            marketing_cost=marketing_cost,
            other_expense=other_expense,
            source=source,
            status="CONFIRMATION_PENDING",
        )

        # ===================================
        # FINANCIALS
        # ===================================

        order.total_cost = OrderIntelligenceService.calculate_total_cost(order)

        order.net_profit = OrderIntelligenceService.calculate_net_profit(order)

        order.profit_margin = OrderIntelligenceService.calculate_profit_margin(order)

        # ===================================
        # PRODUCT ANALYTICS
        # ===================================

        product.total_orders += quantity

        # ===================================
        # SAVE ORDER
        # ===================================

        db.add(order)

        db.commit()

        db.refresh(order)

        # ===================================
        # CREATE ORDER ITEM
        # ===================================

        order_item = OrderItem(
            order_id=order.id,
            product_name=product.name,
            normalized_name=(
                ProductNormalizationService.normalize_product_name(product.name)
                if product.name
                else "unknown product"
            ),
            sku=product.sku,
            variant=product.size,
            size=product.size,
            quantity=quantity,
            unit_price=float(product.selling_price or 0),
            total_price=float(selling_price or 0),
            unit_cost=float(product.buying_price or 0),
            total_cost=float(product_cost or 0),
            profit=float(order.net_profit or 0),
        )

        db.add(order_item)

        db.commit()

        # ===================================
        # CLOSE DB
        # ===================================

        db.close()

        return {
            "success": True,
            "message": "Order created successfully",
            "order": order,
        }
