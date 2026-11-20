import asyncio

from datetime import datetime

from app.core.database import SessionLocal

from app.models.order_model import Order

from app.models.product_model import Product

from app.services.order_intelligence_service import OrderIntelligenceService

from app.events.order_events import OrderEvents
from app.core.tenant_context import tenant_scope


class DiscordOrderService:

    # ===================================
    # UPDATE ORDER STATUS
    # ===================================

    @staticmethod
    def update_order_status(
        internal_order_id: str,
        status: str,
        business_id: int,
        discord_channel: str = None,
    ):
        if isinstance(business_id, bool) or business_id <= 0:
            raise ValueError("A valid business ID is required for Discord order updates.")
        with tenant_scope(business_id):
            return DiscordOrderService._update_order_status_scoped(
                internal_order_id, status, business_id, discord_channel
            )

    @staticmethod
    def _update_order_status_scoped(
        internal_order_id: str,
        status: str,
        business_id: int,
        discord_channel: str = None,
    ):

        db = SessionLocal()

        try:

            # ===================================
            # FIND ORDER
            # ===================================

            order = (
                db.query(Order)
                .filter(Order.internal_order_id == internal_order_id)
                .first()
            )

            if not order:

                return {"error": "Order not found"}

            previous_status = order.status

            # ===================================
            # UPDATE STATUS
            # ===================================

            order.status = status

            # ===================================
            # PERMANENT CONFIRMATION DATE
            # ===================================

            if status == "CONFIRMED" and not order.confirmed_order_date:

                order.confirmed_order_date = datetime.utcnow()

            if discord_channel:

                order.discord_channel = discord_channel

            # ===================================
            # PRODUCT ANALYTICS
            # ===================================

            product = db.query(Product).filter(Product.sku == order.sku).first()

            if product:

                # ===============================
                # DELIVERED
                # ===============================

                if status == "DELIVERED" and previous_status != "DELIVERED":

                    product.delivered_orders += order.quantity

                # ===============================
                # CANCELLED
                # ===============================

                elif status == "CANCELLED" and previous_status != "CANCELLED":

                    product.cancelled_orders += order.quantity

                # ===============================
                # RETURNED
                # ===============================

                elif status == "RETURNED" and previous_status != "RETURNED":

                    product.returned_orders += order.quantity

                # ===============================
                # HEALTH SCORE
                # ===============================

                total_orders = max(1, product.total_orders)

                success_rate = (product.delivered_orders / total_orders) * 100

                product.health_score = round(success_rate, 2)

                # ===============================
                # SCALING SCORE
                # ===============================

                product.scaling_score = round(
                    (success_rate * product.total_orders) / 10, 2
                )

            # ===================================
            # ORDER FINANCIAL RECALCULATION
            # ===================================

            order.total_cost = OrderIntelligenceService.calculate_total_cost(order)

            order.net_profit = OrderIntelligenceService.calculate_net_profit(order)

            order.profit_margin = OrderIntelligenceService.calculate_profit_margin(
                order
            )

            # ===================================
            # SAVE
            # ===================================

            db.commit()

            db.refresh(order)

            try:

                loop = asyncio.get_running_loop()

                loop.create_task(
                    OrderEvents.order_updated(
                        {
                            "id": order.id,
                            "business_id": business_id,
                            "internal_order_id": order.internal_order_id,
                            "customer_name": order.customer_name,
                            "customer_phone": order.customer_phone,
                            "city": order.city,
                            "address": order.address,
                            "product_name": order.product_name,
                            "sku": order.sku,
                            "size": order.size,
                            "quantity": order.quantity,
                            "weight_kg": order.weight_kg,
                            "selling_price": order.selling_price,
                            "product_cost": order.product_cost,
                            "delivery_cost": order.delivery_cost,
                            "packaging_cost": order.packaging_cost,
                            "marketing_cost": order.marketing_cost,
                            "other_expense": order.other_expense,
                            "total_cost": order.total_cost,
                            "net_profit": order.net_profit,
                            "profit_margin": order.profit_margin,
                            "source": order.source,
                            "status": order.status,
                            "discord_created_at": (
                                order.discord_created_at.isoformat()
                                if order.discord_created_at
                                else None
                            ),
                            "confirmed_order_date": (
                                order.confirmed_order_date.isoformat()
                                if order.confirmed_order_date
                                else None
                            ),
                            "created_at": (
                                order.created_at.isoformat()
                                if order.created_at
                                else None
                            ),
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    )
                )

            except RuntimeError:

                print("[NO ACTIVE EVENT LOOP]")

            return {
                "message": "Order updated successfully",
                "order_id": internal_order_id,
                "status": status,
            }

        finally:

            db.close()

    # ===================================
    # STATUS MAPPING
    # ===================================

    @staticmethod
    def map_channel_to_status(channel_name: str):

        mapping = {
            "confirmation-orders": "PENDING",
            "active-orders": "ACTIVE",
            "completed-orders": "DELIVERED",
            "cancelled-orders": "CANCELLED",
            "returned-orders": "RETURNED",
        }

        return mapping.get(channel_name, "PENDING")
