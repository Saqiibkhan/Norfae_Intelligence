from app.core.database import SessionLocal

from app.models.order_model import Order

from app.models.order_item_model import (
    OrderItem
)

db = SessionLocal()

orders = db.query(Order).all()

created = 0

for order in orders:

    # ===============================
    # SKIP EXISTING
    # ===============================

    if order.items:

        continue

    # ===============================
    # CREATE ORDER ITEM
    # ===============================

    order_item = OrderItem(

        order_id=order.id,

        product_name=order.product_name,

        normalized_name=(

            order.product_name.lower().strip()

            if order.product_name
            else "unknown"
        ),

        sku=order.sku,

        size=order.size,

        quantity=order.quantity,

        unit_price=float(
            order.selling_price or 0
        ),

        total_price=float(
            order.selling_price or 0
        ),

        unit_cost=float(
            order.product_cost or 0
        ),

        total_cost=float(
            order.product_cost or 0
        ),

        profit=float(
            order.net_profit or 0
        )
    )

    db.add(order_item)

    created += 1

db.commit()

print(
    f"Created {created} missing order items"
)

db.close()