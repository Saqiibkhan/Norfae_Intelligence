from collections import Counter, defaultdict
from datetime import datetime, timezone
from math import isfinite
from statistics import median

from sqlalchemy.orm import Session

from app.models import Order, Product
from app.schemas.intelligence_schema import (
    DataQualityIssue,
    DataQualityReport,
    NormalizationPreview,
)


def _number_is_invalid(value) -> bool:
    if value is None:
        return False
    try:
        return not isfinite(float(value)) or float(value) < 0
    except (TypeError, ValueError, OverflowError):
        return True


class DataQualityService:
    """Read-only checks and correction suggestions for one authorized business."""

    @staticmethod
    def analyze(db: Session, business_id: int) -> DataQualityReport:
        # Explicit predicates are retained even though TenantSession also scopes ORM.
        orders = db.query(Order).filter(Order.business_id == business_id).all()
        products = db.query(Product).filter(Product.business_id == business_id).all()
        issues: list[DataQualityIssue] = []
        missing: Counter[str] = Counter()
        duplicates: Counter[str] = Counter()
        invalid_record_keys: set[tuple[str, int]] = set()
        warnings: list[str] = []
        recommendations: list[str] = []
        normalization_preview: list[NormalizationPreview] = []

        def add(record_type, record, code, field, message, suggested_value=None, *, invalid=True):
            issues.append(DataQualityIssue(
                record_type=record_type,
                record_id=getattr(record, "id", None),
                code=code,
                field=field,
                message=message,
                suggested_value=suggested_value,
            ))
            if invalid:
                invalid_record_keys.add((record_type, getattr(record, "id", id(record))))

        for order in orders:
            for field in ("internal_order_id", "product_name", "sku"):
                value = getattr(order, field, None)
                if value is None or (isinstance(value, str) and not value.strip()):
                    missing[f"order.{field}"] += 1
                    add("order", order, "missing_value", field, f"Order is missing {field}.")
            if not any((order.confirmed_order_date, order.discord_created_at)):
                missing["order.source_order_date"] += 1
                add("order", order, "missing_value", "source_order_date", "No confirmed or source order date is recorded.")
            if not isinstance(order.quantity, int) or order.quantity <= 0:
                add("order", order, "invalid_quantity", "quantity", "Order quantity must be a positive integer.")
            for field in ("selling_price", "product_cost", "delivery_cost", "packaging_cost", "marketing_cost", "other_expense"):
                value = getattr(order, field, None)
                if value is None:
                    missing[f"order.{field}"] += 1
                    add("order", order, "missing_value", field, f"Order is missing {field}.")
                elif _number_is_invalid(value):
                    add("order", order, "invalid_amount", field, f"{field} must be a finite non-negative amount.")
            order_date = order.confirmed_order_date or order.discord_created_at or order.created_at
            if order_date and order_date.replace(tzinfo=None) > datetime.now(timezone.utc).replace(tzinfo=None):
                add("order", order, "future_date", "order_date", "Order timestamp is in the future.")
            status = (order.status or "").strip().upper()
            if not status:
                missing["order.status"] += 1
                add("order", order, "missing_value", "status", "Order status is missing.")
            elif status not in {"PENDING", "CONFIRMATION_PENDING", "PROCESSING", "DELIVERED", "CANCELLED", "RETURNED"}:
                add("order", order, "unknown_status", "status", "Order status is not in the known status set.")
            if order.internal_order_id and order.internal_order_id != order.internal_order_id.strip():
                add("order", order, "normalization_suggestion", "internal_order_id", "Order ID contains surrounding whitespace.", order.internal_order_id.strip())

        order_ids: dict[str, list[Order]] = defaultdict(list)
        for order in orders:
            if order.internal_order_id and order.internal_order_id.strip():
                order_ids[order.internal_order_id.strip().casefold()].append(order)
        for group in order_ids.values():
            if len(group) > 1:
                duplicates["orders.internal_order_id"] += len(group) - 1
                for order in group:
                    add("order", order, "duplicate_order_id", "internal_order_id", "Internal order ID duplicates another order in this business.")

        for product in products:
            for field in ("name", "sku"):
                value = getattr(product, field, None)
                if value is None or not value.strip():
                    missing[f"product.{field}"] += 1
                    add("product", product, "missing_value", field, f"Product is missing {field}.")
            for field in ("buying_price", "selling_price", "stock"):
                if getattr(product, field, None) is None:
                    missing[f"product.{field}"] += 1
                    add("product", product, "missing_value", field, f"Product is missing {field}.")
            for field in ("buying_price", "selling_price", "weight_kg", "stock"):
                if _number_is_invalid(getattr(product, field, None)):
                    add("product", product, "invalid_amount", field, f"Product {field} must be finite and non-negative.")
            for field in ("name", "sku"):
                value = getattr(product, field, None)
                if value and value != value.strip():
                    add("product", product, "normalization_suggestion", field, f"Product {field} contains surrounding whitespace.", value.strip())
            normalized_product = {}
            if product.name and product.name != product.name.strip():
                normalized_product["name"] = product.name.strip()
            if product.sku and product.sku != product.sku.strip():
                normalized_product["sku"] = product.sku.strip()
            if normalized_product:
                normalization_preview.append(NormalizationPreview(
                    record_type="product", record_id=product.id,
                    normalized_fields=normalized_product,
                ))

        skus: dict[str, list[Product]] = defaultdict(list)
        for product in products:
            if product.sku and product.sku.strip():
                skus[product.sku.strip().casefold()].append(product)
        for group in skus.values():
            if len(group) > 1:
                duplicates["products.sku_case_insensitive"] += len(group) - 1
                for product in group:
                    add("product", product, "duplicate_sku", "sku", "SKU duplicates another product after case and whitespace normalization.")

        known_skus = {p.sku.strip().casefold(): p for p in products if p.sku and p.sku.strip()}
        for order in orders:
            if order.sku and order.sku.strip() and order.sku.strip().casefold() not in known_skus:
                add("order", order, "unmatched_sku", "sku", "Order SKU does not match a product in this business.")
            elif order.sku and order.sku.strip():
                matched_product = known_skus[order.sku.strip().casefold()]
                if matched_product.sku != order.sku:
                    add("order", order, "inconsistent_sku", "sku", "Order SKU matches a product only after case/whitespace normalization.", matched_product.sku)
            normalized_order = {}
            if order.internal_order_id and order.internal_order_id != order.internal_order_id.strip():
                normalized_order["internal_order_id"] = order.internal_order_id.strip()
            if order.product_name and order.product_name != order.product_name.strip():
                normalized_order["product_name"] = order.product_name.strip()
            if order.status and order.status != order.status.strip().upper():
                normalized_order["status"] = order.status.strip().upper()
            if order.sku and order.sku.strip():
                matched_product = known_skus.get(order.sku.strip().casefold())
                normalized_sku = matched_product.sku.strip() if matched_product else order.sku.strip().upper()
                if normalized_sku != order.sku:
                    normalized_order["sku"] = normalized_sku
            if normalized_order:
                normalization_preview.append(NormalizationPreview(
                    record_type="order", record_id=order.id,
                    normalized_fields=normalized_order,
                ))

        numeric_groups = (
            ("order.quantity", [("order", row, _numeric(row.quantity)) for row in orders]),
            ("order.selling_price", [("order", row, _numeric(row.selling_price)) for row in orders]),
            ("product.selling_price", [("product", row, _numeric(row.selling_price)) for row in products]),
        )
        for field, records in numeric_groups:
            values = sorted(value for _, _, value in records if value is not None)
            if len(values) < 4:
                continue
            center = median(values)
            deviations = sorted(abs(value - center) for value in values)
            mad = median(deviations)
            if mad <= 0:
                continue
            for record_type, record, value in records:
                if value is not None and abs(value - center) > 6 * mad:
                    add(record_type, record, "unusual_value", field, "Value is unusually far from this business's median; review its source.", invalid=False)
                    warnings.append(f"Unusual values were detected in {field}.")

        if any(issue.code == "normalization_suggestion" for issue in issues):
            recommendations.append("Review suggested trimmed identifiers and apply corrections only through an explicit, audited data update.")
        if duplicates:
            recommendations.append("Resolve duplicate order IDs and product SKUs before relying on record-level aggregation.")
        if any(issue.code.startswith("invalid_") for issue in issues):
            recommendations.append("Correct invalid quantities and financial values at their source; no records were modified by this analysis.")
        if any(issue.code == "missing_value" for issue in issues):
            recommendations.append("Complete required identifiers, statuses, names, SKUs, and dates where the source data is available.")
        if any(issue.code == "unmatched_sku" for issue in issues):
            recommendations.append("Match order SKUs to the correct business product or repair the imported identifier.")
        if any(issue.code == "inconsistent_sku" for issue in issues):
            recommendations.append("Standardize order SKU casing and whitespace to match the business product catalog.")
        if len(orders) == 0 or len(products) == 0:
            warnings.append("One or more inspected record types contain no records.")
        total = len(orders) + len(products)
        invalid = len(invalid_record_keys)
        return DataQualityReport(
            business_id=business_id,
            generated_at=datetime.now(timezone.utc),
            total_records_inspected=total,
            valid_records=max(0, total - invalid),
            invalid_records=invalid,
            missing_fields=dict(missing),
            duplicate_records=dict(duplicates),
            warnings=warnings,
            recommended_corrections=recommendations,
            normalization_preview=normalization_preview,
            issues=issues,
        )


def _numeric(value):
    if value is None:
        return None
    try:
        parsed = float(value)
        return parsed if isfinite(parsed) else None
    except (TypeError, ValueError, OverflowError):
        return None
