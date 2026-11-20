from app.core.database import SessionLocal

from app.models.order_item_model import OrderItem

db = SessionLocal()

try:

    print("RESETTING ORDER RECALCULATION...")

    order_items = db.query(OrderItem).all()

    for item in order_items:

        item.inventory_product_id = None

        item.unit_cost = 0

        item.total_cost = 0

        item.profit = 0

    db.commit()

    print(f"RESET {len(order_items)} ORDER ITEMS")

finally:

    db.close()
