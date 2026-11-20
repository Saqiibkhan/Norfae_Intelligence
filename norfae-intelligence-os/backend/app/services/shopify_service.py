import requests
from sqlalchemy.orm import Session

from app.models.settings_model import SettingsModel
from app.utils.shopify_url import normalize_shopify_store_url


SHOPIFY_STATUS_TIMEOUT_SECONDS = 5

class ShopifyService:


    # ===================================
    # GET SHOPIFY SETTINGS
    # ===================================

    @staticmethod
    def get_shopify_settings(db: Session, business_id: int):
        return (
            db.query(SettingsModel)
            .filter(SettingsModel.business_id == business_id)
            .first()
        )

    # ===================================
    # SHOPIFY STATUS
    # ===================================

    @staticmethod
    def service_status(db: Session, business_id: int):
        settings = ShopifyService.get_shopify_settings(db, business_id)

        if (
            not settings
            or not settings.shopify_store_url
            or not settings.shopify_access_token
        ):

            return {

                "service": "shopify",

                "initialized": True,

                "connected": False,

                "store": None,

                "message": (
                    "Shopify credentials missing"
                )
            }

        base = {"service": "shopify", "initialized": True}
        try:
            origin = normalize_shopify_store_url(settings.shopify_store_url)
        except (TypeError, ValueError):
            return {**base, "connected": False, "store": None,
                    "message": "Shopify store URL is invalid."}

        url = f"{origin}/admin/api/2026-04/shop.json"
        headers = {"X-Shopify-Access-Token": settings.shopify_access_token}
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=SHOPIFY_STATUS_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                message = "Shopify redirected the status request; redirects are not followed."
            elif response.status_code != 200:
                message = "Shopify status request failed."
            else:
                try:
                    shop_data = response.json()
                except (ValueError, requests.RequestException):
                    message = "Shopify returned an invalid response."
                else:
                    shop = shop_data.get("shop") if isinstance(shop_data, dict) else None
                    if not isinstance(shop, dict):
                        message = "Shopify returned an invalid response."
                    else:
                        return {
                            **base,
                            "connected": True,
                            "store": shop.get("name"),
                            "message": "Shopify connected successfully",
                        }
        except requests.Timeout:
            message = "Shopify status request timed out."
        except requests.RequestException:
            message = "Shopify status request could not connect."
        except Exception:
            message = "Shopify status request failed."

        return {**base, "connected": False, "store": None, "message": message}
