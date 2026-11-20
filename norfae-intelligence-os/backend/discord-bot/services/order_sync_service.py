import sys
import os

import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from app.events.order_events import OrderEvents

from app.core.database import SessionLocal

from app.models.order_model import Order

from app.models.order_item_model import OrderItem

from app.models.settings_model import SettingsModel

from app.services.delivery_cost_service import DeliveryCostService

from app.services.product_normalization_service import ProductNormalizationService

from app.services.city_normalization_service import CityNormalizationService

from app.services.city_province_service import CityProvinceService

from app.services.order_display_service import OrderDisplayService

from app.services.inventory_match_service import InventoryMatchService

print("\n========================")
print("ORDER SYNC FILE LOADED")
print(__file__)
print("========================\n")


class OrderSyncService:

    # ===================================
    # CREATE OR UPDATE ORDER
    # ===================================

    @staticmethod
    def upsert_order(
        parsed_order, status, discord_channel, discord_message_id, message_created_at
    ):

        db = SessionLocal()
        print("UPSERT_ORDER EXECUTING")

        try:

            # ===================================
            # FIND EXISTING ORDER
            # ===================================

            existing_order = (
                db.query(Order)
                .filter(Order.internal_order_id == parsed_order["order_id"])
                .first()
            )

            # ===================================
            # UPDATE EXISTING ORDER
            # ===================================

            if existing_order:

                existing_order.status = status

                existing_order.discord_channel = discord_channel

                existing_order.discord_message_id = str(discord_message_id)

                # ===================================
                # UPDATE EDITED DATA
                # ===================================

                existing_order.customer_name = parsed_order.get("customer_name")

                print("SETTING NAME TO:", parsed_order.get("customer_name"))
                print("MODEL NAME NOW:", existing_order.customer_name)

                existing_order.customer_phone = parsed_order.get("phone")

                existing_order.address = parsed_order.get("address")

                normalized_city = CityNormalizationService.normalize_city(
                    parsed_order.get("city")
                )

                existing_order.city = normalized_city

                existing_order.province = CityProvinceService.get_province(
                    normalized_city
                )
                existing_order.source = parsed_order.get("source")

                existing_order.selling_price = float(parsed_order.get("total", 0) or 0)

                existing_order.updated_at = message_created_at

                # ===================================
                # DELETE OLD ORDER ITEMS
                # ===================================

                db.query(OrderItem).filter(
                    OrderItem.order_id == existing_order.id
                ).delete()

                # ===================================
                # RESET TOTALS
                # ===================================

                total_product_cost = 0

                total_weight = 0

                total_inventory_selling = 0

                all_skus = []

                products = parsed_order.get("products", [])

                is_multi_product = len(products) > 1

                settings = db.query(SettingsModel).first()

                selling_price = float(parsed_order.get("total", 0) or 0)

                # ===================================
                # REBUILD ORDER ITEMS
                # ===================================

                for item in products:

                    item_name = item.get("name", "")

                    quantity = int(item.get("quantity", 1))

                    item_size = item.get("size")

                    normalized_item = (
                        ProductNormalizationService.normalize_product_name(item_name)
                    )

                    matched_inventory = (
                        InventoryMatchService.find_matching_inventory_product(
                            db=db,
                            product_name=item_name,
                            selling_price=selling_price,
                            size=item_size,
                            is_multi_product=is_multi_product,
                        )
                    )

                    item_sku = "UNKNOWN"

                    unit_cost = 0

                    item_weight = 0

                    inventory_selling = 0

                    allocated_selling_price = 0

                    if matched_inventory:

                        item_sku = str(matched_inventory.sku)

                        unit_cost = float(matched_inventory.product_cost or 0)

                        item_weight = float(matched_inventory.weight_kg or 0)

                        inventory_selling = float(matched_inventory.selling_price or 0)

                        allocated_selling_price = inventory_selling * quantity

                    item_total_cost = unit_cost * quantity

                    total_product_cost += item_total_cost

                    total_weight += item_weight * quantity

                    total_inventory_selling += allocated_selling_price

                    all_skus.append(item_sku)

                    order_item = OrderItem(
                        order_id=existing_order.id,
                        product_name=item_name,
                        normalized_name=normalized_item.lower(),
                        sku=item_sku,
                        size=item_size,
                        quantity=quantity,
                        unit_price=round(
                            allocated_selling_price / max(quantity, 1),
                            2,
                        ),
                        total_price=round(
                            allocated_selling_price,
                            2,
                        ),
                        unit_cost=round(
                            unit_cost,
                            2,
                        ),
                        total_cost=round(
                            item_total_cost,
                            2,
                        ),
                        profit=round(
                            allocated_selling_price - item_total_cost,
                            2,
                        ),
                    )

                    db.add(order_item)

                try:

                    loop = asyncio.get_running_loop()

                    loop.create_task(
                        OrderEvents.order_updated(
                            {
                                "id": existing_order.id,
                                "internal_order_id": existing_order.internal_order_id,
                                "customer_name": existing_order.customer_name,
                                "customer_phone": existing_order.customer_phone,
                                "city": existing_order.city,
                                "address": existing_order.address,
                                "product_name": existing_order.product_name,
                                "sku": existing_order.sku,
                                "size": existing_order.size,
                                "quantity": existing_order.quantity,
                                "weight_kg": existing_order.weight_kg,
                                "selling_price": existing_order.selling_price,
                                "product_cost": existing_order.product_cost,
                                "delivery_cost": existing_order.delivery_cost,
                                "packaging_cost": existing_order.packaging_cost,
                                "marketing_cost": existing_order.marketing_cost,
                                "other_expense": existing_order.other_expense,
                                "total_cost": existing_order.total_cost,
                                "net_profit": existing_order.net_profit,
                                "profit_margin": existing_order.profit_margin,
                                "source": existing_order.source,
                                "status": existing_order.status,
                                "discord_created_at": (
                                    existing_order.discord_created_at.isoformat()
                                    if existing_order.discord_created_at
                                    else None
                                ),
                                "confirmed_order_date": (
                                    existing_order.confirmed_order_date.isoformat()
                                    if existing_order.confirmed_order_date
                                    else None
                                ),
                                "created_at": (
                                    existing_order.created_at.isoformat()
                                    if existing_order.created_at
                                    else None
                                ),
                                "updated_at": (
                                    existing_order.updated_at.isoformat()
                                    if existing_order.updated_at
                                    else None
                                ),
                            }
                        )
                    )

                except RuntimeError:

                    print("[NO ACTIVE EVENT LOOP]")
                print("SETTING NAME TO:", parsed_order.get("customer_name"))

                print("EXISTING NAME BEFORE COMMIT:", existing_order.customer_name)

                db.flush()

                print("FLUSH COMPLETE")
                print("BEFORE COMMIT")

                db.commit()

                print("AFTER COMMIT")

                db.refresh(existing_order)

                print("AFTER REFRESH NAME:", existing_order.customer_name)

                print(f"Updated Order: " f"{existing_order.internal_order_id}")

                return existing_order

            # ===================================
            # SETTINGS
            # ===================================

            settings = db.query(SettingsModel).first()

            # ===================================
            # SELLING PRICE
            # ===================================

            selling_price = float(parsed_order.get("total", 0) or 0)

            # ===================================
            # PACKAGING COST
            # ===================================

            packaging_cost = 50

            if settings and settings.packaging_cost:

                packaging_cost = float(settings.packaging_cost)

            # ===================================
            # DISPLAY PRODUCT NAME
            # ===================================

            display_product_name = OrderDisplayService.generate_order_display_name(
                parsed_order.get("products", [])
            )

            # ===================================
            # CREATE ORDER
            # ===================================

            normalized_city = CityNormalizationService.normalize_city(
                parsed_order.get("city")
            )

            province = CityProvinceService.get_province(normalized_city)

            print("CITY:", normalized_city)
            print("PROVINCE:", province)

            print("========== NEW ORDER ==========")
            print("ORDER ID:", parsed_order.get("order_id"))
            print("CITY:", normalized_city)
            print("PROVINCE:", province)
            print("==============================")

            new_order = Order(
                internal_order_id=parsed_order["order_id"],
                discord_message_id=str(discord_message_id),
                discord_channel=discord_channel,
                customer_name=parsed_order.get("customer_name"),
                customer_phone=parsed_order.get("phone"),
                city=normalized_city,
                province=province,
                address=parsed_order.get("address"),
                product_name=display_product_name,
                sku="",
                size=parsed_order.get("size"),
                quantity=1,
                weight_kg=0,
                selling_price=round(selling_price, 2),
                product_cost=0,
                delivery_cost=0,
                packaging_cost=round(packaging_cost, 2),
                marketing_cost=0,
                other_expense=0,
                total_cost=0,
                net_profit=0,
                profit_margin=0,
                source=parsed_order.get("source"),
                status=status,
                created_at=message_created_at,
                discord_created_at=message_created_at,
                updated_at=message_created_at,
            )

            db.add(new_order)

            db.commit()

            db.refresh(new_order)

            # ===================================
            # AGGREGATE TOTALS
            # ===================================

            total_product_cost = 0

            total_weight = 0

            total_inventory_selling = 0

            all_skus = []

            # ===================================
            # MULTI PRODUCT DETECTION
            # ===================================

            is_multi_product = len(parsed_order.get("products", [])) > 1

            # ===================================
            # PROCESS PRODUCTS
            # ===================================

            for item in parsed_order.get("products", []):

                item_name = item.get("name", "")

                quantity = int(item.get("quantity", 1))

                item_size = item.get("size")

                normalized_item = ProductNormalizationService.normalize_product_name(
                    item_name
                )

                # ===================================
                # INVENTORY MATCHING
                # ===================================

                matched_inventory = (
                    InventoryMatchService.find_matching_inventory_product(
                        db=db,
                        product_name=item_name,
                        selling_price=selling_price,
                        size=item_size,
                        is_multi_product=is_multi_product,
                    )
                )

                # ===================================
                # DEFAULT VALUES
                # ===================================

                item_sku = "UNKNOWN"

                unit_cost = 0

                item_weight = 0

                inventory_selling = 0

                allocated_selling_price = 0

                # ===================================
                # MATCHED INVENTORY
                # ===================================

                if matched_inventory:

                    item_sku = str(matched_inventory.sku)

                    unit_cost = float(matched_inventory.product_cost or 0)

                    item_weight = float(matched_inventory.weight_kg or 0)

                    inventory_selling = float(matched_inventory.selling_price or 0)

                    allocated_selling_price = inventory_selling * quantity

                # ===================================
                # CALCULATIONS
                # ===================================

                item_total_cost = unit_cost * quantity

                total_product_cost += item_total_cost

                total_weight += item_weight * quantity

                total_inventory_selling += allocated_selling_price

                all_skus.append(item_sku)

                # ===================================
                # CREATE ORDER ITEM
                # ===================================

                order_item = OrderItem(
                    order_id=new_order.id,
                    product_name=item_name,
                    normalized_name=normalized_item.lower(),
                    sku=item_sku,
                    size=item_size,
                    quantity=quantity,
                    unit_price=round(allocated_selling_price / max(quantity, 1), 2),
                    total_price=round(allocated_selling_price, 2),
                    unit_cost=round(unit_cost, 2),
                    total_cost=round(item_total_cost, 2),
                    profit=round(allocated_selling_price - item_total_cost, 2),
                )

                db.add(order_item)

            # ===================================
            # FINAL PRICE VALIDATION
            # ===================================

            price_difference = abs(total_inventory_selling - selling_price)

            if price_difference > 500:

                print(
                    "WARNING: PRICE MISMATCH ->",
                    parsed_order.get("order_id"),
                    total_inventory_selling,
                    selling_price,
                )

            # ===================================
            # UPDATE ORDER TOTALS
            # ===================================

            new_order.product_cost = round(total_product_cost, 2)

            new_order.weight_kg = round(total_weight, 2)

            new_order.sku = ", ".join(all_skus)

            # ===================================
            # DELIVERY COST
            # ===================================

            delivery_cost = 0

            if settings:

                delivery_data = DeliveryCostService.calculate_delivery_cost(
                    city=(
                        CityNormalizationService.normalize_city(
                            parsed_order.get("city")
                        )
                    ),
                    weight_kg=total_weight,
                    order_amount=selling_price,
                    settings=settings,
                )

                if delivery_data.get("success"):

                    delivery_cost = float(delivery_data["delivery_cost"])

            new_order.delivery_cost = round(delivery_cost, 2)

            # ===================================
            # FINAL CALCULATIONS
            # ===================================

            new_order.total_cost = round(
                new_order.product_cost
                + new_order.delivery_cost
                + new_order.packaging_cost
                + new_order.marketing_cost
                + new_order.other_expense,
                2,
            )

            new_order.net_profit = round(
                new_order.selling_price - new_order.total_cost, 2
            )

            if new_order.selling_price > 0:

                new_order.profit_margin = round(
                    (new_order.net_profit / new_order.selling_price) * 100, 2
                )

            db.commit()

            print(f"Created Order: " f"{new_order.internal_order_id}")

            return new_order

        except Exception as error:

            import traceback

            traceback.print_exc()

            print("Order Sync Error:", error)

            db.rollback()

        finally:

            db.close()
