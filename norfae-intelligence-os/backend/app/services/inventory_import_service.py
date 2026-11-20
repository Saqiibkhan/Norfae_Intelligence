from sqlalchemy.orm import Session

from app.models.inventory_product_model import InventoryProduct

from app.services.product_normalization_service import ProductNormalizationService


def import_inventory_excel(file_path: str, db: Session):

    import pandas as pd

    dataframe = pd.read_excel(file_path, header=1)

    imported_count = 0

    updated_count = 0

    # ===================================
    # LOOP PRODUCTS
    # ===================================

    for _, row in dataframe.iterrows():

        # ===================================
        # SKIP EMPTY ROWS
        # ===================================

        if pd.isna(row["Product Name"]):

            continue

        product_name = str(row["Product Name"]).strip()

        if product_name == "" or product_name.lower() == "nan":

            continue

        # ===================================
        # NORMALIZED NAME
        # ===================================

        normalized_name = ProductNormalizationService.normalize_product_name(
            product_name
        )

        # ===================================
        # CLEAN SKU
        # ===================================

        sku = str(row["SKU"]).strip() if pd.notna(row["SKU"]) else ""

        if not sku or sku == "":

            continue

        # ===================================
        # STOCK
        # ===================================

        stock_quantity = int(row["Stock"]) if pd.notna(row["Stock"]) else 0

        # ===================================
        # PRODUCT COST
        # ===================================

        product_cost = (
            float(str(row["Product Cost"]).replace("Rs", "").replace(",", "").strip())
            if pd.notna(row["Product Cost"])
            else 0
        )

        # ===================================
        # SELLING PRICE
        # ===================================

        selling_price = (
            float(
                str(row["Price on Website"]).replace("Rs", "").replace(",", "").strip()
            )
            if pd.notna(row["Price on Website"])
            else 0
        )

        # ===================================
        # SIZE
        # ===================================

        size = str(row["Size"]).strip() if pd.notna(row["Size"]) else ""

        # ===================================
        # AUTO WEIGHT DETECTION
        # ===================================

        size_lower = size.lower()

        weight_kg = 0.5

        if "32" in size_lower:

            weight_kg = 0.24

        elif "40" in size_lower:

            weight_kg = 0.5

        elif "45" in size_lower:

            weight_kg = 0.5

        elif "65" in size_lower:

            weight_kg = 0.5

        # ===================================
        # FIND EXISTING PRODUCT
        # ===================================

        existing_product = (
            db.query(InventoryProduct).filter(InventoryProduct.sku == sku).first()
        )

        # ===================================
        # UPDATE EXISTING PRODUCT
        # ===================================

        if existing_product:

            existing_product.product_name = product_name

            existing_product.normalized_name = normalized_name

            existing_product.category = "Plush Toys"

            existing_product.size = size

            existing_product.stock_quantity = stock_quantity

            # ===================================
            # FINANCIALS
            # ===================================

            existing_product.product_cost = product_cost

            existing_product.selling_price = selling_price

            # ===================================
            # WEIGHT
            # ===================================

            existing_product.weight_kg = weight_kg

            updated_count += 1

        # ===================================
        # CREATE NEW PRODUCT
        # ===================================

        else:

            new_product = InventoryProduct(
                product_name=product_name,
                normalized_name=normalized_name,
                sku=sku,
                category="Plush Toys",
                size=size,
                stock_quantity=stock_quantity,
                # ===================================
                # FINANCIALS
                # ===================================
                product_cost=product_cost,
                selling_price=selling_price,
                # ===================================
                # WEIGHT
                # ===================================
                weight_kg=weight_kg,
            )

            db.add(new_product)

            imported_count += 1

    # ===================================
    # SAVE
    # ===================================

    db.commit()

    return {
        "message": "Inventory imported successfully",
        "new_products": imported_count,
        "updated_products": updated_count,
    }
