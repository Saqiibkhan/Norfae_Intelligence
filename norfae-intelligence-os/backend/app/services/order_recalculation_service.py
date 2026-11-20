from sqlalchemy.orm import Session

from app.models.order_model import Order

from app.models.settings_model import SettingsModel

from app.models.inventory_product_model import InventoryProduct

from app.services.delivery_cost_service import DeliveryCostService

from app.services.order_intelligence_service import OrderIntelligenceService

from app.services.inventory_match_service import InventoryMatchService


class OrderRecalculationService:

    # =====================================
    # RECALCULATE SINGLE ORDER
    # =====================================

    @staticmethod
    def recalculate_order(db: Session, order: Order):

        # =====================================
        # SETTINGS
        # =====================================

        settings = db.query(SettingsModel).first()

        # =====================================
        # DEFAULT TOTALS
        # =====================================

        total_product_cost = 0

        total_weight = 0

        all_skus = []

        # =====================================
        # LOOP ORDER ITEMS
        # =====================================

        for item in order.items:

            inventory_product = None

            # =====================================
            # MANUAL SKU MATCH
            # =====================================

            if item.sku:

                inventory_product = (
                    db.query(InventoryProduct)
                    .filter(InventoryProduct.sku == str(item.sku))
                    .first()
                )

            # =====================================
            # AUTO MATCH FALLBACK
            # =====================================

            if not inventory_product:

                inventory_product = (
                    InventoryMatchService.find_matching_inventory_product(
                        db=db,
                        product_name=item.product_name,
                        selling_price=item.unit_price,
                        size=item.size,
                        is_multi_product=(len(order.items) > 1),
                    )
                )

            # =====================================
            # MATCH FOUND
            # =====================================

            if inventory_product:

                # =====================================
                # UPDATE ITEM DATA
                # =====================================

                item.sku = str(inventory_product.sku)

                item.unit_cost = float(inventory_product.product_cost or 0)

                item.total_cost = round(item.unit_cost * item.quantity, 2)

                # =====================================
                # KEEP ORIGINAL ORDER SELLING
                # =====================================

                original_total_price = float(item.total_price or 0)

                item.profit = round(original_total_price - item.total_cost, 2)

                # =====================================
                # WEIGHT
                # =====================================

                item_weight = float(inventory_product.weight_kg or 0)

                item_quantity = int(item.quantity or 1)

                calculated_weight = item_weight * item_quantity

                total_weight += calculated_weight

                # =====================================
                # PRODUCT COST
                # =====================================

                total_product_cost += float(item.total_cost or 0)

                all_skus.append(str(inventory_product.sku))

            # =====================================
            # NO MATCH
            # =====================================
            else:

                item.sku = "UNMATCHED"

                all_skus.append("UNMATCHED")

        # =====================================
        # UPDATE ORDER CORE VALUES
        # =====================================

        order.product_cost = round(total_product_cost, 2)

        order.weight_kg = round(max(total_weight, 0), 2)

        order.sku = ", ".join(all_skus)

        # =====================================
        # PACKAGING COST
        # =====================================

        packaging_cost = 50

        if settings and settings.packaging_cost:

            packaging_cost = float(settings.packaging_cost)

        # =====================================
        # PRODUCT COUNT
        # =====================================

        product_count = max(len(order.items), 1)

        # =====================================
        # FINAL PACKAGING
        # =====================================

        order.packaging_cost = round(packaging_cost * product_count, 2)

        # =====================================
        # DELIVERY RECALCULATION
        # =====================================

        try:

            delivery_data = DeliveryCostService.calculate_delivery_cost(
                city=order.city,
                weight_kg=order.weight_kg,
                order_amount=order.selling_price,
                settings=settings,
            )

            if delivery_data.get("success"):

                order.delivery_cost = round(float(delivery_data["delivery_cost"]), 2)

            else:

                order.delivery_cost = 0

        except Exception as error:

            print("Delivery Error:", error)

            order.delivery_cost = 0

        # =====================================
        # FINAL INTELLIGENCE
        # =====================================

        order.total_cost = OrderIntelligenceService.calculate_total_cost(order)

        order.net_profit = OrderIntelligenceService.calculate_net_profit(order)

        order.profit_margin = OrderIntelligenceService.calculate_profit_margin(order)

        # =====================================
        # SAVE
        # =====================================

        db.commit()

        db.refresh(order)

        return order

    # =====================================
    # RECALCULATE ALL ORDERS
    # =====================================

    @staticmethod
    def recalculate_all_orders(db: Session):

        orders = db.query(Order).all()

        updated_orders = 0

        failed_orders = 0

        for order in orders:

            try:

                OrderRecalculationService.recalculate_order(db=db, order=order)

                updated_orders += 1

            except Exception as error:

                failed_orders += 1

                print(f"Failed Order: " f"{order.id}", error)

        return {
            "success": True,
            "updated_orders": updated_orders,
            "failed_orders": failed_orders,
        }
