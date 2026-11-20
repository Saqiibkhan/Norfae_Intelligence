import requests  # Kept as an importable patch point for existing status checks/tests.

from app.models.settings_model import SettingsModel
from app.services.shopify_client import ShopifyAPIError, ShopifyClient, SHOPIFY_TIMEOUT

SHOPIFY_STATUS_TIMEOUT_SECONDS = 5


class ShopifyService:
    @staticmethod
    def get_shopify_settings(db, business_id: int):
        return db.query(SettingsModel).filter(SettingsModel.business_id == business_id).first()

    @staticmethod
    def service_status(db, business_id: int):
        settings = ShopifyService.get_shopify_settings(db, business_id)
        if not settings or not settings.shopify_store_url or not settings.shopify_access_token:
            return {"service": "shopify", "initialized": True, "connected": False,
                    "store": None, "message": "Shopify credentials missing"}
        try:
            client = ShopifyClient(settings.shopify_store_url, settings.shopify_access_token,
                                   timeout=SHOPIFY_STATUS_TIMEOUT_SECONDS)
            body = client.get_json("shop")
            shop = body.get("shop")
            if not isinstance(shop, dict):
                raise ShopifyAPIError("invalid_response", "Shopify returned an invalid response.")
            store_name = shop.get("name")
            if not isinstance(store_name, str):
                store_name = None
            return {"service": "shopify", "initialized": True, "connected": True,
                    "store": store_name, "message": "Shopify connected successfully"}
        except ValueError:
            message = "Shopify store URL is invalid."
        except ShopifyAPIError as error:
            message = {
                "timeout": "Shopify status request timed out.",
                "network_error": "Shopify status request could not connect.",
                "request_error": "Shopify status request could not connect.",
                "invalid_response": "Shopify returned an invalid response.",
                "redirect_rejected": "Shopify redirected the status request; redirects are not followed.",
                "authentication_failed": "Shopify status request failed.",
            }.get(error.category, "Shopify status request failed.")
        except Exception:
            message = "Shopify status request failed."
        return {"service": "shopify", "initialized": True, "connected": False,
                "store": None, "message": message}
