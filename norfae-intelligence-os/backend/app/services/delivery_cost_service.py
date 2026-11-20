from math import ceil

from app.models.settings_model import (
    SettingsModel
)

from app.services.city_province_service import (
    CityProvinceService
)

class DeliveryCostService:


    # =========================================
    # CALCULATE DELIVERY COST
    # =========================================

    @staticmethod
    def calculate_delivery_cost(

        city: str,

        weight_kg: float,

        order_amount: float,

        settings
    ) -> dict:

        if weight_kg <= 0:

            return {

                "success": False,

                "message":
                    "Weight must be greater than 0"
            }

        normalized_city = (
                city.lower().strip()
            )

        warehouse_city = (
                settings
                .warehouse_city
                .lower()
                .strip()
            )

        warehouse_province = (
                settings
                .warehouse_province
                .lower()
                .strip()
            )

        customer_province = (

                CityProvinceService
                .get_province(
                    normalized_city
                )
                .lower()
                .strip()
            )

        # =====================================
        # DETECT DELIVERY TYPE
        # =====================================

        if normalized_city == warehouse_city:

                zone = "same_city"

        elif customer_province == warehouse_province:

                zone = "same_province"

        else:

                zone = "other_province"

        # =====================================
        # DYNAMIC SETTINGS RATES
        # =====================================

        if zone == "same_city":

            rates = {

                "first_half_kg":
                    settings.same_city_half_kg,

                "first_1kg":
                    settings.same_city_one_kg,

                "additional_half_kg":
                    settings
                    .same_city_additional_half_kg
            }

        elif zone == "same_province":

            rates = {

                "first_half_kg":
                    settings.same_province_half_kg,

                "first_1kg":
                    settings.same_province_one_kg,

                "additional_half_kg":
                    settings
                    .same_province_additional_half_kg
            }

        else:

            rates = {

                "first_half_kg":
                    settings.other_province_half_kg,

                "first_1kg":
                    settings.other_province_one_kg,

                "additional_half_kg":
                    settings
                    .other_province_additional_half_kg
            }

        # =====================================
        # BASE PARCEL CHARGES
        # =====================================

        if weight_kg <= 0.5:

            parcel_charges = (
                rates["first_half_kg"]
            )

        elif weight_kg <= 1:

            parcel_charges = (
                rates["first_1kg"]
            )

        else:

            extra_weight = (
                weight_kg - 1
            )

            additional_slabs = ceil(
                extra_weight / 0.5
            )

            parcel_charges = (

                rates["first_1kg"]

                +

                (
                    additional_slabs
                    *
                    rates[
                        "additional_half_kg"
                    ]
                )
            )

        # =====================================
        # FUEL SURCHARGE
        # =====================================

        fuel_surcharge = (

            parcel_charges *

            (
                settings
                .fuel_surcharge_percentage
                / 100
            )
        )

        subtotal = (

            parcel_charges +

            fuel_surcharge
        )

        # =====================================
        # GST
        # =====================================

        gst_amount = (

            subtotal *

            (
                settings
                .gst_percentage
                / 100
            )
        )

        total_delivery_cost = (

            subtotal +

            gst_amount
        )

        # =====================================
        # COD INCOME TAX
        # =====================================

        cod_tax = (

            order_amount *

            (
                settings
                .income_tax_percentage
                / 100
            )
        )

        total_delivery_cost += cod_tax

        # =====================================
        # RESPONSE
        # =====================================

        return {

            "success": True,

            "city": city,

            "zone": zone,

            "weight_kg": weight_kg,

            "parcel_charges": round(
                parcel_charges,
                2
            ),

            "fuel_surcharge": round(
                fuel_surcharge,
                2
            ),

            "gst_amount": round(
                gst_amount,
                2
            ),

            "cod_tax": round(
                cod_tax,
                2
            ),

            "delivery_cost": round(
                total_delivery_cost,
                2
            )
        }