from app.models.inventory_product_model import (
    InventoryProduct
)

from app.services.product_normalization_service import (
    ProductNormalizationService
)


class SKUMatchingService:

    @staticmethod
    def match_inventory_product(
        db,
        order_item
    ):

        # ===================================
        # SKU MATCHING
        # ===================================

        if order_item.sku:

            inventory_product = (
                db.query(InventoryProduct)
                .filter(
                    InventoryProduct.sku
                    == order_item.sku
                )
                .first()
            )

            if inventory_product:

                return inventory_product

        # ===================================
        # NAME NORMALIZATION MATCHING
        # ===================================

        normalized_name = (
            ProductNormalizationService
            .normalize_product_name(
                order_item.product_name
            )
        )

        inventory_product = (
            db.query(InventoryProduct)
            .filter(
                InventoryProduct.normalized_name
                == normalized_name
            )
            .first()
        )

        return inventory_product