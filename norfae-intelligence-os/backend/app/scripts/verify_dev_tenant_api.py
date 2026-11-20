"""Verify core tenant routes against the configured local development owner."""

import os
from pathlib import Path

import httpx
from dotenv import dotenv_values


BACKEND_ROOT = Path(__file__).resolve().parents[2]
API_BASE_URL = os.getenv("NORFAE_DEV_API_BASE_URL", "http://127.0.0.1:8001").rstrip("/")


def main() -> None:
    config = dotenv_values(BACKEND_ROOT / ".env")
    email = config.get("NORFAE_DEV_OWNER_EMAIL")
    password = config.get("NORFAE_DEV_OWNER_PASSWORD")
    business_name = config.get("NORFAE_DEV_BUSINESS_NAME")
    if not email or not password or not business_name:
        raise SystemExit("Development identity variables are missing from the local .env.")

    with httpx.Client(base_url=API_BASE_URL, timeout=15.0) as client:
        health = client.get("/health")
        docs = client.get("/docs")
        login = client.post("/auth/login", json={"email": email, "password": password})
        if health.status_code != 200 or docs.status_code != 200 or login.status_code != 200:
            raise SystemExit("Health, docs, or development-owner login verification failed.")

        auth_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        profile = client.get("/auth/me", headers=auth_headers)
        businesses = client.get("/businesses", headers=auth_headers)
        if profile.status_code != 200 or businesses.status_code != 200:
            raise SystemExit("Authenticated profile or business listing verification failed.")
        matches = [item for item in businesses.json() if item["name"] == business_name]
        if len(matches) != 1 or matches[0]["role"] != "owner":
            raise SystemExit("Could not resolve the configured development business membership.")
        business_id = matches[0]["id"]
        tenant_headers = {**auth_headers, "X-Business-ID": str(business_id)}

        business = client.get(f"/businesses/{business_id}", headers=auth_headers)
        settings = client.get("/settings/", headers=tenant_headers)
        expenses = client.get("/expenses/?filter_type=all", headers=tenant_headers)
        products = client.get("/products/", headers=tenant_headers)
        orders = client.get("/orders/", headers=tenant_headers)
        forged = client.get(
            "/expenses/?filter_type=all",
            headers={**auth_headers, "X-Business-ID": str(business_id + 1_000_000)},
        )

        if any(r.status_code != 200 for r in (business, settings, expenses, products, orders)):
            raise SystemExit("A selected-business or business-data API check failed.")
        if forged.status_code != 404:
            raise SystemExit("A non-member business selection was not rejected.")
        if len(expenses.json()) != 2:
            raise SystemExit("The business does not see exactly the two backfilled expenses.")
        if "shopify_access_token" in settings.json() or "meta_access_token" in settings.json():
            raise SystemExit("A settings response exposed an integration credential field.")

        print(
            "Development tenant API verified: "
            f"business_id={business_id}, settings=200, expenses={len(expenses.json())}, "
            f"products={products.status_code}, orders={orders.status_code}, forged_business={forged.status_code}."
        )


if __name__ == "__main__":
    main()
