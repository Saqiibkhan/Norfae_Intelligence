from typing import Optional

from fastapi import Query

from fastapi import APIRouter

from pydantic import BaseModel

from app.core.database import SessionLocal

from app.models.product_model import Product

from app.models.inventory_product_model import InventoryProduct

from app.services.order_recalculation_service import OrderRecalculationService

router = APIRouter(prefix="/products", tags=["Products"])

# ===================================
# REQUEST MODEL
# ===================================


class ProductCreate(BaseModel):

    name: str

    sku: str

    category: str

    size: str

    website_size: str

    weight_kg: float

    buying_price: float

    selling_price: float

    stock: int


# ===================================
# GET PRODUCTS
# ===================================


@router.get("/")
def get_products(category: Optional[str] = Query(None)):

    db = SessionLocal()

    query = db.query(Product)

    if category:

        query = query.filter(Product.category == category)

    products = query.order_by(Product.sku.asc()).all()

    db.close()

    return products


# ===================================
# CREATE PRODUCT
# ===================================


@router.post("/")
def create_product(product: ProductCreate):

    db = SessionLocal()

    existing_product = db.query(Product).filter(Product.sku == product.sku).first()

    if existing_product:

        db.close()

        return {"error": "SKU already exists"}

    # ===================================
    # CREATE PRODUCT
    # ===================================

    new_product = Product(
        name=product.name,
        sku=product.sku,
        category=product.category,
        size=product.size,
        website_size=product.website_size,
        weight_kg=product.weight_kg,
        buying_price=product.buying_price,
        selling_price=product.selling_price,
        stock=product.stock,
    )

    db.add(new_product)

    # ===================================
    # CREATE INVENTORY PRODUCT
    # ===================================

    inventory_product = InventoryProduct(
        product_name=product.name,
        normalized_name=product.name.lower().strip(),
        sku=product.sku,
        category=product.category,
        size=product.size,
        stock_quantity=product.stock,
        product_cost=product.buying_price,
        selling_price=product.selling_price,
        weight_kg=product.weight_kg,
    )

    db.add(inventory_product)

    db.commit()

    db.refresh(new_product)

    db.close()

    return {"message": "Product created successfully", "product": new_product}


# ===================================
# UPDATE PRODUCT
# ===================================


@router.put("/{product_id}")
def update_product(product_id: int, data: dict):

    db = SessionLocal()

    try:

        # ===================================
        # FIND PRODUCT
        # ===================================

        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:

            db.close()

            return {"error": "Product not found"}

        # ===================================
        # UPDATE PRODUCT TABLE
        # ===================================

        for key, value in data.items():

            setattr(product, key, value)

        # ===================================
        # FIND INVENTORY PRODUCT
        # ===================================

        inventory_product = (
            db.query(InventoryProduct)
            .filter(InventoryProduct.sku == product.sku)
            .first()
        )

        # ===================================
        # REALTIME INVENTORY SYNC
        # ===================================

        if inventory_product:

            inventory_product.product_name = product.name

            inventory_product.normalized_name = product.name.lower().strip()

            inventory_product.category = product.category

            inventory_product.size = product.size

            inventory_product.stock_quantity = product.stock

            inventory_product.product_cost = float(product.buying_price or 0)

            inventory_product.selling_price = float(product.selling_price or 0)

            inventory_product.weight_kg = float(product.weight_kg or 0)

        # ===================================
        # SAVE
        # ===================================

        db.commit()

        db.refresh(product)

        # ===================================
        # RECALCULATE ALL ORDERS
        # ===================================

        OrderRecalculationService.recalculate_all_orders(db)

        return {"message": "Product updated successfully", "product": product}

    except Exception as error:

        db.rollback()

        return {"error": str(error)}

    finally:

        db.close()


# ===================================
# DELETE PRODUCT
# ===================================


@router.delete("/{product_id}")
def delete_product(product_id: int):

    db = SessionLocal()

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:

        db.close()

        return {"error": "Product not found"}

    # ===================================
    # DELETE INVENTORY PRODUCT
    # ===================================

    inventory_product = (
        db.query(InventoryProduct).filter(InventoryProduct.sku == product.sku).first()
    )

    if inventory_product:

        db.delete(inventory_product)

    # ===================================
    # DELETE PRODUCT
    # ===================================

    db.delete(product)

    db.commit()

    db.close()

    return {"message": "Product deleted successfully"}
