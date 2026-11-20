class OrderDisplayService:

    @staticmethod
    def generate_order_display_name(
        products: list
    ):

        if not products:

            return "Unknown Product"

        formatted_products = []

        for item in products:

            # =========================
            # PRODUCT OBJECT
            # =========================

            if isinstance(item, dict):

                product_name = item.get(
                    "name",
                    "Unknown Product"
                )

                quantity = item.get(
                    "quantity",
                    1
                )

                formatted_products.append(
                    f"{product_name} x{quantity}"
                )

            # =========================
            # STRING FALLBACK
            # =========================

            else:

                formatted_products.append(
                    str(item)
                )

        # =========================
        # FIRST PRODUCT
        # =========================

        first_product = (
            formatted_products[0]
        )

        remaining = (
            len(formatted_products) - 1
        )

        # =========================
        # SINGLE PRODUCT
        # =========================

        if remaining <= 0:

            return first_product

        # =========================
        # MULTI PRODUCT
        # =========================

        return (
            f"{first_product} "
            f"+{remaining} more"
        )