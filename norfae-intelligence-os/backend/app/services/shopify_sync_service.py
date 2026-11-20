from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    InventoryProduct, Order, OrderItem, Product, SettingsModel,
    ShopifySyncRun, ShopifySyncState,
)
from app.services.product_normalization_service import ProductNormalizationService
from app.services.shopify_client import ShopifyAPIError, ShopifyClient

OVERLAP = timedelta(minutes=5)
STALE_RUN_AFTER = timedelta(hours=1)


class ShopifySyncError(Exception):
    def __init__(self, category: str, summary: str, status_code: int = 502):
        super().__init__(summary)
        self.category = category
        self.summary = summary
        self.status_code = status_code


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_time(value):
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _shopify_id(value):
    if isinstance(value, bool):
        return None
    text = str(value).strip() if value is not None else ""
    return text if text.isdigit() and int(text) > 0 else None


def _money(value, *, required=False):
    if value is None:
        if required:
            raise ValueError("Missing financial amount")
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Invalid financial amount") from None
    if not number.is_finite() or abs(number) > Decimal("999999999999"):
        raise ValueError("Financial amount is outside the supported range")
    return float(number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _finite_text(value, limit=255):
    return value.strip()[:limit] if isinstance(value, str) and value.strip() else None


def _first_non_null(record: dict, preferred: str, fallback: str):
    return record.get(preferred) if record.get(preferred) is not None else record.get(fallback)


def _safe_shopify_image(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        trusted_host = host in {"cdn.shopify.com", "static.shopify.com"} or host.endswith(".shopifycdn.net")
        if (parsed.scheme == "https" and trusted_host and parsed.port in (None, 443)
                and not parsed.username and not parsed.password and not parsed.fragment):
            return value
    except ValueError:
        pass
    return None


def _total_refunded(refunds):
    if refunds is None:
        return None
    if not isinstance(refunds, list):
        raise ValueError("Invalid Shopify refunds")
    total = Decimal("0")
    for refund in refunds:
        if not isinstance(refund, dict):
            raise ValueError("Invalid Shopify refund")
        transactions = refund.get("transactions", [])
        if not isinstance(transactions, list):
            raise ValueError("Invalid Shopify refund transactions")
        for transaction in transactions:
            if not isinstance(transaction, dict):
                raise ValueError("Invalid Shopify refund transaction")
            if transaction.get("kind") == "refund" and transaction.get("status") == "success":
                amount = _money(transaction.get("amount"), required=True)
                if amount < 0:
                    raise ValueError("Invalid negative refund")
                total += Decimal(str(amount))
    return float(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _safe_cursor_params(cursor):
    if cursor is None:
        return {"limit": 250}
    since = (cursor - OVERLAP).replace(microsecond=0).isoformat() + "Z"
    return {"limit": 250, "updated_at_min": since, "order": "updated_at asc"}


class ShopifySyncService:
    @staticmethod
    def client_for_business(db: Session, business_id: int) -> ShopifyClient:
        settings = db.query(SettingsModel).filter(SettingsModel.business_id == business_id).first()
        if not settings or not settings.shopify_store_url or not settings.shopify_access_token:
            raise ShopifySyncError("configuration_missing", "Shopify credentials are not configured.", 409)
        try:
            return ShopifyClient(settings.shopify_store_url, settings.shopify_access_token)
        except (ValueError, ShopifyAPIError):
            raise ShopifySyncError("configuration_invalid", "Shopify integration settings are invalid.", 409) from None

    @staticmethod
    def _begin(db: Session, business_id: int, user_id: int, sync_type: str):
        now = _utcnow()
        state = db.query(ShopifySyncState).filter(ShopifySyncState.business_id == business_id).with_for_update().first()
        if state is None:
            state = ShopifySyncState(business_id=business_id)
            db.add(state)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                state = db.query(ShopifySyncState).filter(ShopifySyncState.business_id == business_id).with_for_update().first()
        running_field = f"{sync_type}_running_since"
        cursor_field = f"{sync_type}_cursor"
        running_since = getattr(state, running_field)
        if running_since and running_since > now - STALE_RUN_AFTER:
            db.rollback()
            raise ShopifySyncError("sync_in_progress", f"A Shopify {sync_type} sync is already running.", 409)
        if running_since:
            stale_runs = db.query(ShopifySyncRun).filter(
                ShopifySyncRun.business_id == business_id,
                ShopifySyncRun.sync_type == sync_type,
                ShopifySyncRun.status == "running",
            ).all()
            for stale_run in stale_runs:
                stale_run.status = "failed"
                stale_run.completed_at = now
                stale_run.error_category = "lease_expired"
                stale_run.error_summary = "Previous sync stopped before completion."
        cursor_before = getattr(state, cursor_field)
        setattr(state, running_field, now)
        run = ShopifySyncRun(
            business_id=business_id, user_id=user_id, sync_type=sync_type,
            trigger_type="manual", status="running", started_at=now, cursor_before=cursor_before,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return state, run, cursor_before, now

    @staticmethod
    def _finish(db: Session, business_id: int, sync_type: str, run_id: int,
                *, status: str, counts: dict, error: ShopifyAPIError | ShopifySyncError | None = None,
                advance_cursor: datetime | None = None):
        state = db.query(ShopifySyncState).filter(ShopifySyncState.business_id == business_id).with_for_update().first()
        run = db.query(ShopifySyncRun).filter(ShopifySyncRun.id == run_id, ShopifySyncRun.business_id == business_id).with_for_update().first()
        if state is None or run is None:
            raise ShopifySyncError("database_error", "Shopify sync state could not be finalized.", 500)
        setattr(state, f"{sync_type}_running_since", None)
        if advance_cursor is not None:
            setattr(state, f"{sync_type}_cursor", advance_cursor)
            run.cursor_after = advance_cursor
        run.status = status
        run.completed_at = _utcnow()
        run.records_fetched = counts.get("fetched", 0)
        run.records_created = counts.get("created", 0)
        run.records_updated = counts.get("updated", 0)
        run.records_skipped = counts.get("skipped", 0)
        if error:
            run.error_category = error.category
            run.error_summary = error.summary[:300]
        db.commit()
        return ShopifySyncService._run_response(run)

    @staticmethod
    def _run_response(run):
        return {
            "run_id": run.id, "sync_type": run.sync_type, "status": run.status,
            "trigger_type": run.trigger_type,
            "records_fetched": run.records_fetched, "records_created": run.records_created,
            "records_updated": run.records_updated, "records_skipped": run.records_skipped,
            "error_category": run.error_category, "message": run.error_summary,
            "started_at": run.started_at.isoformat() + "Z",
            "completed_at": run.completed_at.isoformat() + "Z" if run.completed_at else None,
        }

    @staticmethod
    def _fetch(db, business_id, resource, cursor):
        # Serialize store binding with settings changes and other resource syncs.
        state = db.query(ShopifySyncState).filter(
            ShopifySyncState.business_id == business_id
        ).with_for_update().first()
        client = ShopifySyncService.client_for_business(db, business_id)
        domain = urlsplit(client.origin).hostname
        if state.store_domain and state.store_domain != domain:
            completed = db.query(ShopifySyncRun.id).filter(
                ShopifySyncRun.business_id == business_id,
                ShopifySyncRun.status.in_(("completed", "partially_completed")),
            ).first()
            if completed:
                raise ShopifySyncError(
                    "store_changed",
                    "This business has already synchronized a different Shopify store. Reconnect the original store or arrange a reviewed data reset before switching stores.",
                    409,
                )
            state.products_cursor = None
            state.orders_cursor = None
        if state.store_domain != domain:
            state.store_domain = domain
            db.commit()
        params = _safe_cursor_params(cursor)
        if resource == "orders":
            params["status"] = "any"
            params["fields"] = "id,name,created_at,updated_at,financial_status,fulfillment_status,currency,current_total_price,current_subtotal_price,current_total_discounts,current_total_tax,total_price,subtotal_price,total_discounts,total_tax,cancelled_at,shipping_address,shipping_lines,line_items,refunds"
        elif resource == "products":
            params["status"] = "any"
            params["fields"] = "id,title,body_html,product_type,vendor,status,created_at,updated_at,variants,image"
        return client.get_pages(resource, params)

    @staticmethod
    def sync_products(db: Session, business_id: int, user_id: int):
        state, run, cursor, started = ShopifySyncService._begin(db, business_id, user_id, "products")
        counts = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0}
        try:
            products = ShopifySyncService._fetch(db, business_id, "products", cursor)
            prepared = []
            seen_variants = set()
            for product in products:
                product_id = _shopify_id(product.get("id"))
                variants = product.get("variants")
                if not product_id or not isinstance(variants, list):
                    counts["skipped"] += 1
                    continue
                title = _finite_text(product.get("title"), 500)
                if not title:
                    counts["skipped"] += max(1, len(variants))
                    continue
                product_updated = _parse_time(product.get("updated_at"))
                product_created = _parse_time(product.get("created_at"))
                if product_updated is None:
                    counts["skipped"] += max(1, len(variants))
                    continue
                product_type = _finite_text(product.get("product_type"))
                status = _finite_text(product.get("status"), 40)
                image_payload = product.get("image")
                image_url = _safe_shopify_image(image_payload.get("src")) if isinstance(image_payload, dict) else None
                for variant in variants:
                    variant_id = _shopify_id(variant.get("id")) if isinstance(variant, dict) else None
                    if not variant_id or variant_id in seen_variants:
                        counts["skipped"] += 1
                        continue
                    seen_variants.add(variant_id)
                    try:
                        price = _money(variant.get("price"), required=True)
                        compare_at_price = _money(variant.get("compare_at_price"))
                        if price < 0 or (compare_at_price is not None and compare_at_price < 0):
                            raise ValueError("Negative product price")
                        inventory = variant.get("inventory_quantity")
                        if inventory is not None and (isinstance(inventory, bool) or int(inventory) != inventory):
                            raise ValueError("Invalid inventory quantity")
                        inventory = int(inventory) if inventory is not None else None
                    except (ValueError, TypeError, InvalidOperation):
                        counts["skipped"] += 1
                        continue
                    prepared.append({
                        "product_id": product_id, "variant_id": variant_id,
                        "title": title, "product_type": product_type,
                        "vendor": _finite_text(product.get("vendor")), "status": status,
                        "description": _finite_text(product.get("body_html"), 10000),
                        "image_url": image_url,
                        "created_at": product_created,
                        "updated_at": _parse_time(variant.get("updated_at")) or product_updated,
                        "sku": _finite_text(variant.get("sku"), 255),
                        "variant": _finite_text(variant.get("title"), 255),
                        "price": price, "inventory": inventory,
                        "compare_at_price": compare_at_price,
                    })
            counts["fetched"] = len(prepared) + counts["skipped"]
            # Query once, then key solely by Shopify variant identity.
            variant_ids = [p["variant_id"] for p in prepared]
            inventory_by_id = {x.shopify_variant_id: x for x in db.query(InventoryProduct).filter(InventoryProduct.shopify_variant_id.in_(variant_ids)).all()} if variant_ids else {}
            products_by_id = {x.shopify_variant_id: x for x in db.query(Product).filter(Product.shopify_variant_id.in_(variant_ids)).all()} if variant_ids else {}
            for row in prepared:
                inv = inventory_by_id.get(row["variant_id"])
                prod = products_by_id.get(row["variant_id"])
                if inv is None:
                    inv = ShopifySyncService._find_manual_inventory(db, row["sku"])
                    if inv is not None:
                        inv.shopify_product_id = row["product_id"]
                        inv.shopify_variant_id = row["variant_id"]
                        inventory_by_id[row["variant_id"]] = inv
                if prod is None:
                    prod = ShopifySyncService._find_manual_product(db, row["sku"])
                    if prod is not None:
                        prod.shopify_product_id = row["product_id"]
                        prod.shopify_variant_id = row["variant_id"]
                        products_by_id[row["variant_id"]] = prod
                creating = inv is None and prod is None
                chosen_sku = row["sku"]
                if chosen_sku:
                    inv_conflict = db.query(InventoryProduct).filter(InventoryProduct.sku == chosen_sku).first()
                    product_conflict = db.query(Product).filter(Product.sku == chosen_sku).first()
                    if inv_conflict is not None and inv_conflict.shopify_variant_id != row["variant_id"]:
                        chosen_sku = None
                    if product_conflict is not None and product_conflict.shopify_variant_id != row["variant_id"]:
                        chosen_sku = None
                variant_title = row["variant"]
                if variant_title and variant_title.casefold() == "default title":
                    variant_title = None
                if inv is None:
                    inv = InventoryProduct(
                        shopify_product_id=row["product_id"], shopify_variant_id=row["variant_id"],
                        product_name=row["title"], normalized_name=ProductNormalizationService.normalize_product_name(row["title"]),
                        sku=chosen_sku, shopify_sku=row["sku"], category=row["product_type"],
                        variant=variant_title, stock_quantity=row["inventory"], product_cost=None,
                        selling_price=row["price"], shopify_status=row["status"], shopify_updated_at=row["updated_at"],
                        shopify_created_at=row["created_at"], shopify_compare_at_price=row["compare_at_price"],
                        shopify_image_url=row["image_url"],
                    )
                    inv.shopify_created_at = row["created_at"]
                    db.add(inv)
                    inventory_by_id[row["variant_id"]] = inv
                else:
                    ShopifySyncService._update_inventory(inv, row, variant_title, chosen_sku)
                if prod is None:
                    prod = Product(
                        name=row["title"], sku=chosen_sku, shopify_sku=row["sku"],
                        shopify_product_id=row["product_id"], shopify_variant_id=row["variant_id"],
                        shopify_status=row["status"], shopify_updated_at=row["updated_at"],
                        category=row["product_type"], size=variant_title, website_size=variant_title,
                        buying_price=None, selling_price=row["price"], stock=row["inventory"], weight_kg=None,
                        shopify_description=row["description"], shopify_vendor=row["vendor"],
                        shopify_created_at=row["created_at"], shopify_compare_at_price=row["compare_at_price"],
                        shopify_image_url=row["image_url"],
                    )
                    if row["created_at"]:
                        prod.created_at = row["created_at"]
                    db.add(prod)
                    products_by_id[row["variant_id"]] = prod
                else:
                    ShopifySyncService._update_product(prod, row, variant_title, chosen_sku)
                counts["created" if creating else "updated"] += 1
            db.flush()
            status = "partially_completed" if counts["skipped"] else "completed"
            return ShopifySyncService._finish(
                db, business_id, "products", run.id, status=status, counts=counts,
                advance_cursor=None if counts["skipped"] else started,
                error=ShopifySyncError("invalid_records", "Some Shopify product or variant records were skipped.") if counts["skipped"] else None,
            )
        except (ShopifyAPIError, ShopifySyncError) as error:
            db.rollback()
            err = error if isinstance(error, ShopifySyncError) else ShopifySyncError(error.category, error.safe_summary)
            return ShopifySyncService._finish(db, business_id, "products", run.id, status="failed", counts=counts, error=err)
        except Exception:
            db.rollback()
            err = ShopifySyncError("database_error", "Shopify product sync failed; no changes from this run were retained.", 500)
            try:
                return ShopifySyncService._finish(db, business_id, "products", run.id, status="failed", counts=counts, error=err)
            except Exception:
                raise err from None

    @staticmethod
    def _find_manual_inventory(db, sku):
        if not sku:
            return None
        rows = db.query(InventoryProduct).filter(InventoryProduct.sku == sku, InventoryProduct.shopify_variant_id.is_(None)).limit(2).all()
        return rows[0] if len(rows) == 1 else None

    @staticmethod
    def _find_manual_product(db, sku):
        if not sku:
            return None
        rows = db.query(Product).filter(Product.sku == sku, Product.shopify_variant_id.is_(None)).limit(2).all()
        return rows[0] if len(rows) == 1 else None

    @staticmethod
    def _update_inventory(inv, row, variant_title, chosen_sku):
        inv.product_name = row["title"]
        inv.normalized_name = ProductNormalizationService.normalize_product_name(row["title"])
        inv.shopify_product_id = row["product_id"]
        inv.shopify_variant_id = row["variant_id"]
        inv.shopify_sku = row["sku"]
        inv.sku = chosen_sku or inv.sku
        inv.category = row["product_type"] or inv.category
        inv.variant = variant_title or inv.variant
        inv.selling_price = row["price"]
        if row["inventory"] is not None:
            inv.stock_quantity = row["inventory"]
        inv.shopify_status = row["status"] or inv.shopify_status
        inv.shopify_updated_at = row["updated_at"] or inv.shopify_updated_at
        inv.shopify_created_at = row["created_at"] or inv.shopify_created_at
        inv.shopify_compare_at_price = row["compare_at_price"] if row["compare_at_price"] is not None else inv.shopify_compare_at_price
        inv.shopify_image_url = row["image_url"] or inv.shopify_image_url

    @staticmethod
    def _update_product(prod, row, variant_title, chosen_sku):
        prod.name = row["title"]
        prod.shopify_product_id = row["product_id"]
        prod.shopify_variant_id = row["variant_id"]
        prod.shopify_sku = row["sku"]
        prod.sku = chosen_sku or prod.sku
        prod.category = row["product_type"] or prod.category
        prod.size = variant_title or prod.size
        prod.website_size = variant_title or prod.website_size
        prod.selling_price = row["price"]
        if row["inventory"] is not None:
            prod.stock = row["inventory"]
        prod.shopify_status = row["status"] or prod.shopify_status
        prod.shopify_updated_at = row["updated_at"] or prod.shopify_updated_at
        prod.shopify_created_at = row["created_at"] or prod.shopify_created_at
        prod.shopify_description = row["description"] or prod.shopify_description
        prod.shopify_vendor = row["vendor"] or prod.shopify_vendor
        prod.shopify_compare_at_price = row["compare_at_price"] if row["compare_at_price"] is not None else prod.shopify_compare_at_price
        prod.shopify_image_url = row["image_url"] or prod.shopify_image_url

    @staticmethod
    def sync_orders(db: Session, business_id: int, user_id: int):
        state, run, cursor, started = ShopifySyncService._begin(db, business_id, user_id, "orders")
        counts = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0}
        try:
            provider_orders = ShopifySyncService._fetch(db, business_id, "orders", cursor)
            prepared, seen = [], set()
            for order in provider_orders:
                order_id = _shopify_id(order.get("id"))
                lines = order.get("line_items")
                if not order_id or order_id in seen or not isinstance(lines, list):
                    counts["skipped"] += 1
                    continue
                seen.add(order_id)
                created_at = _parse_time(order.get("created_at"))
                updated_at = _parse_time(order.get("updated_at"))
                if created_at is None or updated_at is None:
                    counts["skipped"] += 1
                    continue
                parsed_lines = []
                seen_line_ids = set()
                bad = False
                for line in lines:
                    line_id = _shopify_id(line.get("id")) if isinstance(line, dict) else None
                    quantity = line.get("quantity") if isinstance(line, dict) else None
                    try:
                        parsed_quantity = int(quantity)
                        if isinstance(quantity, bool) or str(parsed_quantity) != str(quantity):
                            raise ValueError("Invalid line item quantity")
                        quantity = parsed_quantity
                        price = _money(line.get("price"), required=True)
                        if quantity <= 0 or not line_id or line_id in seen_line_ids:
                            raise ValueError("Invalid line item identity or quantity")
                        discount = _money(line.get("total_discount")) or 0
                        if price < 0 or discount < 0:
                            raise ValueError("Negative line item amount")
                    except (ValueError, TypeError, InvalidOperation):
                        bad = True
                        break
                    line_title = _finite_text(line.get("title"), 500) or _finite_text(line.get("name"), 500)
                    if not line_title:
                        bad = True
                        break
                    parsed_lines.append({
                        "id": line_id, "product_id": _shopify_id(line.get("product_id")),
                        "variant_id": _shopify_id(line.get("variant_id")),
                        "title": line_title,
                        "sku": _finite_text(line.get("sku")), "quantity": quantity,
                        "unit_price": price, "discount": discount,
                    })
                    seen_line_ids.add(line_id)
                if bad:
                    counts["skipped"] += 1
                    continue
                try:
                    total = _money(_first_non_null(order, "current_total_price", "total_price"), required=True)
                    original_total = _money(_first_non_null(order, "total_price", "current_total_price"), required=True)
                    subtotal = _money(_first_non_null(order, "current_subtotal_price", "subtotal_price"))
                    discounts = _money(_first_non_null(order, "current_total_discounts", "total_discounts"))
                    taxes = _money(_first_non_null(order, "current_total_tax", "total_tax"))
                    if total < 0:
                        raise ValueError("Negative order total")
                    currency = _finite_text(order.get("currency"), 3)
                    if currency and not re.fullmatch(r"[A-Za-z]{3}", currency):
                        raise ValueError("Invalid currency code")
                    shipping_lines = order.get("shipping_lines")
                    shipping = None
                    if shipping_lines is not None:
                        if not isinstance(shipping_lines, list):
                            raise ValueError("Invalid shipping lines")
                        shipping = sum((_money(x.get("price"), required=True) for x in shipping_lines if isinstance(x, dict)), 0.0)
                        if len([x for x in shipping_lines if isinstance(x, dict)]) != len(shipping_lines):
                            raise ValueError("Invalid shipping line")
                    refunded = _total_refunded(order.get("refunds"))
                except (ValueError, TypeError, InvalidOperation):
                    counts["skipped"] += 1
                    continue
                prepared.append({
                    "id": order_id, "updated_at": updated_at,
                    "created_at": created_at, "total": total, "original_total": original_total,
                    "subtotal": subtotal, "discounts": discounts, "taxes": taxes,
                    "shipping": shipping,
                    "refunded": refunded,
                    "name": _finite_text(order.get("name"), 100),
                    "currency": currency.upper() if currency else None,
                    "financial_status": _finite_text(order.get("financial_status"), 40),
                    "fulfillment_status": _finite_text(order.get("fulfillment_status"), 40),
                    "cancelled_at": _parse_time(order.get("cancelled_at")),
                    "city": _finite_text((order.get("shipping_address") or {}).get("city"), 120) if isinstance(order.get("shipping_address") or {}, dict) else None,
                    "province": _finite_text((order.get("shipping_address") or {}).get("province_code") or (order.get("shipping_address") or {}).get("province"), 120) if isinstance(order.get("shipping_address") or {}, dict) else None,
                    "lines": parsed_lines,
                })
            line_owners = {}
            duplicate_line_orders = set()
            for record in prepared:
                for line in record["lines"]:
                    prior_owner = line_owners.setdefault(line["id"], record["id"])
                    if prior_owner != record["id"]:
                        duplicate_line_orders.add(record["id"])
                        duplicate_line_orders.add(prior_owner)
            if duplicate_line_orders:
                counts["skipped"] += len(duplicate_line_orders)
                prepared = [record for record in prepared if record["id"] not in duplicate_line_orders]
            counts["fetched"] = len(prepared) + counts["skipped"]
            order_ids = [x["id"] for x in prepared]
            existing_orders = {x.shopify_order_id: x for x in db.query(Order).filter(Order.shopify_order_id.in_(order_ids)).all()} if order_ids else {}
            variant_ids = list({line["variant_id"] for x in prepared for line in x["lines"] if line["variant_id"]})
            inv_by_variant = {x.shopify_variant_id: x for x in db.query(InventoryProduct).filter(InventoryProduct.shopify_variant_id.in_(variant_ids)).all()} if variant_ids else {}
            line_ids = [line["id"] for x in prepared for line in x["lines"]]
            existing_items = {x.shopify_line_item_id: x for x in db.query(OrderItem).filter(OrderItem.shopify_line_item_id.in_(line_ids)).all()} if line_ids else {}
            for data in prepared:
                order = existing_orders.get(data["id"])
                creating = order is None
                if creating:
                    order = Order(
                        internal_order_id=f"SHOPIFY-{data['id']}", shopify_order_id=data["id"],
                        source="shopify", status="PENDING", customer_name=None,
                        customer_phone=None, address=None,
                        weight_kg=None, product_cost=None, delivery_cost=None,
                        packaging_cost=None, marketing_cost=None, other_expense=None,
                        total_cost=None, net_profit=None, profit_margin=None,
                    )
                    db.add(order)
                    db.flush()
                    existing_orders[data["id"]] = order
                order.shopify_order_id = data["id"]
                order.shopify_order_name = data["name"] or order.shopify_order_name
                order.shopify_updated_at = data["updated_at"] or order.shopify_updated_at
                order.shopify_currency = data["currency"] or order.shopify_currency
                order.shopify_financial_status = data["financial_status"] or order.shopify_financial_status
                order.shopify_fulfillment_status = data["fulfillment_status"] or order.shopify_fulfillment_status
                order.shopify_total_price = data["total"]
                order.shopify_original_total_price = data["original_total"]
                order.shopify_subtotal_price = data["subtotal"] if data["subtotal"] is not None else order.shopify_subtotal_price
                order.shopify_total_discounts = data["discounts"] if data["discounts"] is not None else order.shopify_total_discounts
                order.shopify_total_tax = data["taxes"] if data["taxes"] is not None else order.shopify_total_tax
                order.shopify_total_refunded = data["refunded"] if data["refunded"] is not None else order.shopify_total_refunded
                order.shopify_shipping_price = data["shipping"] if data["shipping"] is not None else order.shopify_shipping_price
                order.shopify_cancelled_at = data["cancelled_at"] or order.shopify_cancelled_at
                order.selling_price = data["total"]
                if data["created_at"]:
                    order.confirmed_order_date = data["created_at"]
                order.city = data["city"] or order.city
                order.province = data["province"] or order.province
                order.source = "shopify"
                order.status = ShopifySyncService._map_order_status(data)
                titles = list(dict.fromkeys(line["title"] for line in data["lines"]))
                skus = list(dict.fromkeys(line["sku"] for line in data["lines"] if line["sku"]))
                order.product_name = ", ".join(titles)[:1000] or order.product_name
                order.sku = ", ".join(skus)[:1000] or None
                order.quantity = sum(line["quantity"] for line in data["lines"])
                known_cost_total = Decimal("0")
                costs_known = True
                current_line_ids = set()
                for line in data["lines"]:
                    current_line_ids.add(line["id"])
                    inv = inv_by_variant.get(line["variant_id"])
                    unit_cost = _money(inv.product_cost) if inv and inv.product_cost is not None else None
                    total_price = max(0, line["unit_price"] * line["quantity"] - line["discount"])
                    item = existing_items.get(line["id"])
                    item_is_new = item is None
                    if item is None:
                        item = OrderItem(order_id=order.id, shopify_line_item_id=line["id"])
                        db.add(item)
                        existing_items[line["id"]] = item
                    item.order_id = order.id
                    item.shopify_line_item_id = line["id"]
                    item.shopify_product_id = line["product_id"]
                    item.shopify_variant_id = line["variant_id"]
                    item.inventory_product_id = inv.id if inv else None
                    item.product_name = line["title"]
                    item.normalized_name = ProductNormalizationService.normalize_product_name(line["title"])
                    item.sku = line["sku"]
                    item.quantity = line["quantity"]
                    item.unit_price = line["unit_price"]
                    item.total_price = total_price
                    item.shopify_discount = line["discount"]
                    if item_is_new or (item.unit_cost is None and unit_cost is not None):
                        item.unit_cost = unit_cost
                        item.total_cost = round(unit_cost * line["quantity"], 2) if unit_cost is not None else None
                    item.profit = round(total_price - item.total_cost, 2) if item.total_cost is not None else None
                    if item.total_cost is None:
                        costs_known = False
                    else:
                        known_cost_total += Decimal(str(item.total_cost))
                # Remove only previously synchronized lines missing from this authoritative order snapshot.
                prior_lines = db.query(OrderItem).filter(OrderItem.order_id == order.id, OrderItem.shopify_line_item_id.isnot(None)).all()
                for item in prior_lines:
                    if item.shopify_line_item_id not in current_line_ids:
                        db.delete(item)
                if creating or (order.product_cost is None and costs_known):
                    order.product_cost = float(known_cost_total) if costs_known else None
                counts["created" if creating else "updated"] += 1
            db.flush()
            status = "partially_completed" if counts["skipped"] else "completed"
            return ShopifySyncService._finish(
                db, business_id, "orders", run.id, status=status, counts=counts,
                advance_cursor=None if counts["skipped"] else started,
                error=ShopifySyncError("invalid_records", "Some Shopify order records were skipped.") if counts["skipped"] else None,
            )
        except (ShopifyAPIError, ShopifySyncError) as error:
            db.rollback()
            err = error if isinstance(error, ShopifySyncError) else ShopifySyncError(error.category, error.safe_summary)
            return ShopifySyncService._finish(db, business_id, "orders", run.id, status="failed", counts=counts, error=err)
        except Exception:
            db.rollback()
            err = ShopifySyncError("database_error", "Shopify order sync failed; no changes from this run were retained.", 500)
            try:
                return ShopifySyncService._finish(db, business_id, "orders", run.id, status="failed", counts=counts, error=err)
            except Exception:
                raise err from None

    @staticmethod
    def _map_order_status(data):
        if data["cancelled_at"]:
            return "CANCELLED"
        financial = (data["financial_status"] or "").casefold()
        if financial == "refunded":
            return "REFUNDED"
        if financial == "partially_refunded":
            return "PARTIALLY_REFUNDED"
        fulfillment = (data["fulfillment_status"] or "").casefold()
        if fulfillment == "fulfilled":
            return "FULFILLED"
        if fulfillment == "partial":
            return "PARTIALLY_FULFILLED"
        return "PROCESSING" if data["financial_status"] else "PENDING"

    @staticmethod
    def sync_all(db: Session, business_id: int, user_id: int):
        run = ShopifySyncRun(
            business_id=business_id, user_id=user_id, sync_type="full",
            trigger_type="manual", status="running", started_at=_utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        try:
            products = ShopifySyncService.sync_products(db, business_id, user_id)
            orders = ShopifySyncService.sync_orders(db, business_id, user_id)
            statuses = {products["status"], orders["status"]}
            status = "completed" if statuses == {"completed"} else "failed" if statuses == {"failed"} else "partially_completed"
            run = db.query(ShopifySyncRun).filter(ShopifySyncRun.id == run.id, ShopifySyncRun.business_id == business_id).first()
            run.status = status
            run.completed_at = _utcnow()
            for key in ("records_fetched", "records_created", "records_updated", "records_skipped"):
                setattr(run, key, products[key] + orders[key])
            errors = [result.get("message") for result in (products, orders) if result.get("message")]
            if errors:
                run.error_category = "partial_sync" if status == "partially_completed" else (products.get("error_category") or orders.get("error_category"))
                run.error_summary = "; ".join(errors)[:300]
            db.commit()
            return {"status": status, "run": ShopifySyncService._run_response(run), "products": products, "orders": orders}
        except ShopifySyncError:
            db.rollback()
            failed_run = db.query(ShopifySyncRun).filter(ShopifySyncRun.id == run.id, ShopifySyncRun.business_id == business_id).first()
            if failed_run:
                failed_run.status = "failed"
                failed_run.completed_at = _utcnow()
                failed_run.error_category = "sync_failed"
                failed_run.error_summary = "Full Shopify synchronization could not complete."
                db.commit()
            raise

    @staticmethod
    def history(db: Session, business_id: int, limit: int = 50):
        rows = db.query(ShopifySyncRun).filter(ShopifySyncRun.business_id == business_id).order_by(ShopifySyncRun.started_at.desc()).limit(limit).all()
        return [ShopifySyncService._run_response(row) for row in rows]
