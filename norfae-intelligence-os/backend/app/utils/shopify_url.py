import ipaddress
import re
from urllib.parse import urlsplit


_SHOPIFY_HOST = re.compile(
    r"^(?=.{1,63}\.myshopify\.com$)[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.myshopify\.com$",
    re.IGNORECASE,
)


def normalize_shopify_store_url(value: str) -> str:
    """Return the canonical HTTPS origin for a supported Shopify store."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("A valid Shopify store domain is required.")
    if any(char in value for char in ("\\", "\r", "\n", "\t")):
        raise ValueError("A valid Shopify store domain is required.")

    candidate = value if "://" in value else f"https://{value}"
    try:
        parsed = urlsplit(candidate)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        raise ValueError("A valid Shopify store domain is required.") from None

    if parsed.scheme.lower() != "https" or not host:
        raise ValueError("Shopify store URLs must use HTTPS.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials are not allowed in Shopify store URLs.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Only a Shopify store domain may be provided.")
    if port not in (None, 443):
        raise ValueError("Unexpected port in Shopify store URL.")

    normalized_host = host.rstrip(".").lower()
    try:
        ipaddress.ip_address(normalized_host)
    except ValueError:
        pass
    else:
        raise ValueError("IP addresses are not valid Shopify store domains.")

    if not _SHOPIFY_HOST.fullmatch(normalized_host):
        raise ValueError("Only *.myshopify.com store domains are supported.")
    return f"https://{normalized_host}"
