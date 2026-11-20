from app.core.database import SessionLocal

from app.models.order_model import Order

from app.services.city_province_service import CityProvinceService

db = SessionLocal()

orders = db.query(Order).all()

updated = 0

for order in orders:

    order.province = CityProvinceService.get_province(order.city)

    updated += 1

db.commit()

db.close()

print(f"Updated {updated} orders")
