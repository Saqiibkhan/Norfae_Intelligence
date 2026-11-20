"""Register the configured development-only owner through the running API.

Credentials must already exist in backend/.env as NORFAE_DEV_OWNER_EMAIL,
NORFAE_DEV_OWNER_PASSWORD, and NORFAE_DEV_BUSINESS_NAME. This utility never
prints credentials, request bodies, or access tokens.
"""

from pathlib import Path
import os

import httpx
from dotenv import dotenv_values


BACKEND_ROOT = Path(__file__).resolve().parents[2]
API_BASE_URL = os.getenv(
    "NORFAE_DEV_API_BASE_URL", "http://127.0.0.1:8001"
).rstrip("/")


def main() -> None:
    config = dotenv_values(BACKEND_ROOT / ".env")
    email = config.get("NORFAE_DEV_OWNER_EMAIL")
    password = config.get("NORFAE_DEV_OWNER_PASSWORD")
    business_name = config.get("NORFAE_DEV_BUSINESS_NAME")
    if not email or not password or not business_name:
        raise SystemExit("Development identity variables are missing from the local .env.")

    with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
        registration = client.post(
            "/auth/register",
            json={
                "email": email,
                "password": password,
                "business_name": business_name,
                "full_name": "Norfae Development Owner",
            },
        )
        if registration.status_code != 201:
            raise SystemExit(
                f"Development owner registration stopped safely (HTTP {registration.status_code})."
            )
        registered = registration.json()
        user_id = registered["user"]["id"]
        business_id = registered["business"]["id"]

        login = client.post("/auth/login", json={"email": email, "password": password})
        if login.status_code != 200:
            raise SystemExit(f"Development owner login verification failed (HTTP {login.status_code}).")
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        profile = client.get("/auth/me", headers=headers)
        businesses = client.get("/businesses", headers=headers)
        detail = client.get(f"/businesses/{business_id}", headers=headers)

        if (
            profile.status_code != 200
            or businesses.status_code != 200
            or detail.status_code != 200
            or not any(item["id"] == business_id for item in businesses.json())
            or "password_hash" in profile.json()
        ):
            raise SystemExit("Registration completed, but authentication or business selection verification failed.")

    print(
        f"Development owner registered and verified: user_id={user_id}, business_id={business_id}."
    )


if __name__ == "__main__":
    main()
