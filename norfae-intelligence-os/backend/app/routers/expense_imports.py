import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.authorization import get_business_context
from app.core.dependencies import get_current_user, get_db
from app.core.timezone import pakistan_now
from app.models import Expense, ExpenseImport, User
from app.models.business_membership_model import BusinessMembership

router = APIRouter(prefix="/expenses/import", tags=["Expense Import"])
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10_000
MAX_FIELD = 1_000
MAX_DESCRIPTION = 255
MAX_REFERENCE = 255
PREVIEW_TTL = timedelta(hours=1)
csv.field_size_limit(MAX_FIELD)


def _error(status: int, message: str):
    raise HTTPException(status_code=status, detail={"code": "csv_import_error", "message": message})


def _safe_filename(filename: str | None) -> str:
    name = (filename or "upload.csv").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .")[:255]
    return name or "upload.csv"


def _expire_previews(db: Session, business_id: int, user_id: int, now: datetime) -> None:
    expired = db.query(ExpenseImport).filter(
        ExpenseImport.business_id == business_id,
        ExpenseImport.user_id == user_id,
        ExpenseImport.status == "preview",
        ExpenseImport.expires_at <= now,
    ).all()
    for item in expired:
        item.status = "expired"
        item.rows_json = "[]"


def _parse_date(raw: str) -> date:
    value = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError("Invalid date; use YYYY-MM-DD, MM/DD/YYYY, or DD/MM/YYYY.")


def _parse_amount(raw: str) -> Decimal:
    value = raw.strip()
    if not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?", value):
        raise ValueError("Invalid amount; use a plain decimal number without currency symbols or separators.")
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError("Invalid amount.") from None
    if not amount.is_finite():
        raise ValueError("Amount must be finite.")
    if amount < 0:
        raise ValueError("Negative expenses are not supported.")
    rounded = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rounded > Decimal("999999999999"):
        raise ValueError("Amount exceeds the supported limit.")
    return rounded


def _read_csv(data: bytes):
    try:
        decoded = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        _error(400, "CSV must be UTF-8 encoded.")
    if not decoded.strip():
        _error(400, "CSV file is empty.")
    if "\x00" in decoded:
        _error(400, "Binary or invalid CSV content is not supported.")
    try:
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        headers = next(reader, None)
        if not headers or not any(h.strip() for h in headers):
            _error(400, "CSV header row is missing.")
        headers = [h.strip() for h in headers]
        if any(not h or len(h) > 255 for h in headers):
            _error(400, "CSV headers must be non-empty and at most 255 characters.")
        if len(set(h.casefold() for h in headers)) != len(headers):
            _error(400, "Duplicate column headers are not supported.")
        rows = []
        for row_number, row in enumerate(reader, start=2):
            if row_number > MAX_ROWS + 1:
                _error(400, f"CSV cannot exceed {MAX_ROWS} data rows.")
            if len(row) != len(headers):
                rows.append({"_row": row_number, "_shape_error": "Row has a different number of columns than the header."})
            else:
                rows.append({"_row": row_number, **dict(zip(headers, row))})
        if not rows:
            _error(400, "CSV contains a header but no data rows.")
        return headers, rows
    except csv.Error:
        _error(400, "Malformed CSV file.")


@router.post("/preview")
async def preview_expense_import(
    file: UploadFile = File(...),
    mapping: str = Form(..., description='JSON mapping, e.g. {"date":"Date","amount":"Total","description":"Details"}'),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: BusinessMembership = Depends(get_business_context),
):
    if not (file.filename or "").lower().endswith(".csv"):
        _error(400, "Only .csv files are supported.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        _error(413, "CSV upload exceeds the 5 MB limit.")
    if not data:
        _error(400, "CSV file is empty.")
    try:
        column_mapping = json.loads(mapping)
    except (TypeError, json.JSONDecodeError):
        _error(400, "Mapping must be a JSON object.")
    allowed = {"date", "amount", "description", "category", "reference"}
    required = {"date", "amount", "description"}
    if not isinstance(column_mapping, dict) or set(column_mapping) - allowed or not required.issubset(column_mapping):
        _error(400, "Mapping must include date, amount, description, with only category/reference optional.")
    if any(not isinstance(v, str) or not v.strip() for v in column_mapping.values()):
        _error(400, "Each mapped source column must be a non-empty header name.")
    if len(set(v.casefold() for v in column_mapping.values())) != len(column_mapping):
        _error(400, "A source column cannot map to multiple target fields.")
    headers, source_rows = _read_csv(data)
    now = datetime.utcnow()
    _expire_previews(db, membership.business_id, user.id, now)
    missing = [value for value in column_mapping.values() if value not in headers]
    if missing:
        _error(400, "Mapped source column does not exist: " + ", ".join(missing))

    fingerprint = hashlib.sha256(data).hexdigest()
    references = set()
    for row in source_rows:
        if "_row" not in row:
            ref = (row.get(column_mapping.get("reference", ""), "") or "").strip() if "reference" in column_mapping else ""
            if ref:
                references.add(ref)
    existing = set()
    if references:
        existing = {r[0] for r in db.query(Expense.external_reference).filter(Expense.external_reference.in_(references)).all()}

    validated = []
    seen_refs = set()
    for row in source_rows:
        number = row["_row"]
        errors = []
        duplicate_reason = None
        if row.get("_shape_error"):
            errors.append(row["_shape_error"])
        values = {}
        for target, source in column_mapping.items():
            raw = row.get(source, "")
            if len(raw) > MAX_FIELD:
                errors.append(f"{target} exceeds {MAX_FIELD} characters.")
                continue
            values[target] = raw.strip()
        parsed_date = None
        amount = None
        if not values.get("date"):
            errors.append("Date is required.")
        else:
            try:
                parsed_date = _parse_date(values["date"])
            except ValueError as exc:
                errors.append(str(exc))
        if not values.get("amount"):
            errors.append("Amount is required.")
        else:
            try:
                amount = _parse_amount(values["amount"])
            except ValueError as exc:
                errors.append(str(exc))
        description = values.get("description", "")
        if not description:
            errors.append("Description is required.")
        elif len(description) > MAX_DESCRIPTION:
            errors.append(f"Description exceeds {MAX_DESCRIPTION} characters.")
        category = values.get("category") or None
        if category is not None and len(category) > 255:
            errors.append("Category exceeds 255 characters.")
        source_ref = values.get("reference") or ""
        if len(source_ref) > MAX_REFERENCE:
            errors.append(f"Reference exceeds {MAX_REFERENCE} characters.")
        if errors:
            validated.append({"row": number, "status": "invalid", "errors": errors})
            continue
        reference = source_ref or f"csv:{fingerprint}:{number}"
        if reference in seen_refs:
            duplicate_reason = "Duplicate reference within uploaded file."
        elif source_ref and source_ref in existing:
            duplicate_reason = "Reference already exists in this business."
        seen_refs.add(reference)
        record = {
            "row": number,
            "date": parsed_date.isoformat(),
            "amount": str(amount),
            "description": description,
            "category": category,
            "reference": reference,
            "source_reference": source_ref or None,
        }
        validated.append({"row": number, "status": "duplicate" if duplicate_reason else "importable", "duplicate_reason": duplicate_reason, "record": record})

    total = len(validated)
    invalid = sum(r["status"] == "invalid" for r in validated)
    duplicates = sum(r["status"] == "duplicate" for r in validated)
    importable = sum(r["status"] == "importable" for r in validated)
    expires = now + PREVIEW_TTL
    summary = {"total_rows": total, "valid_rows": total - invalid, "invalid_rows": invalid, "duplicate_rows": duplicates, "importable_rows": importable, "row_results": validated}
    record = ExpenseImport(
        business_id=membership.business_id, user_id=user.id, status="preview", fingerprint=fingerprint,
        filename=_safe_filename(file.filename), mapping_json=json.dumps(column_mapping),
        summary_json=json.dumps(summary), rows_json=json.dumps(validated), total_rows=total,
        invalid_rows=invalid, duplicate_rows=duplicates, created_at=datetime.utcnow(), expires_at=expires,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"preview_id": record.id, **summary, "expires_at": expires.isoformat() + "Z"}


@router.post("/confirm")
def confirm_expense_import(
    preview_id: int = Form(...),
    confirm: bool = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    membership: BusinessMembership = Depends(get_business_context),
):
    if confirm is not True:
        _error(400, "Explicit confirmation is required.")
    query = db.query(ExpenseImport).filter(ExpenseImport.id == preview_id, ExpenseImport.user_id == user.id, ExpenseImport.business_id == membership.business_id)
    if db.bind.dialect.name == "postgresql":
        query = query.with_for_update()
    preview = query.first()
    if preview is None:
        _error(404, "Import preview not found.")
    if preview.status != "preview":
        _error(409, "This preview has already been confirmed.")
    now = datetime.utcnow()
    if preview.expires_at <= now:
        preview.status = "expired"
        preview.rows_json = "[]"
        db.commit()
        _error(410, "Import preview has expired. Upload the file again.")
    rows = json.loads(preview.rows_json)
    candidates = [r["record"] for r in rows if r.get("status") == "importable"]
    current_refs = {r[0] for r in db.query(Expense.external_reference).filter(Expense.external_reference.in_([r["reference"] for r in candidates])).all()} if candidates else set()
    colliding = [r["reference"] for r in candidates if r["reference"] in current_refs]
    if colliding:
        _error(409, "One or more references now exist in this business. Create a fresh preview to review duplicates.")
    try:
        for row in candidates:
            db.add(Expense(
                title=row["description"], amount=float(Decimal(row["amount"])), category=row["category"],
                source="csv_import", external_reference=row["reference"],
                expense_date=datetime.combine(date.fromisoformat(row["date"]), datetime.min.time()),
            ))
        preview.status = "imported"
        preview.imported_rows = len(candidates)
        preview.imported_at = now
        preview.rows_json = "[]"
        db.commit()
    except IntegrityError:
        db.rollback()
        _error(409, "Import conflicted with an existing expense reference; no rows were imported.")
    except Exception:
        db.rollback()
        _error(500, "Import failed; no rows were imported.")
    return {"preview_id": preview.id, "status": preview.status, "imported_rows": preview.imported_rows, "invalid_rows": preview.invalid_rows, "duplicate_rows": preview.duplicate_rows}


@router.get("/history")
def expense_import_history(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
    membership: BusinessMembership = Depends(get_business_context),
):
    _expire_previews(db, membership.business_id, user.id, datetime.utcnow())
    db.commit()
    imports = db.query(ExpenseImport).filter(
        ExpenseImport.business_id == membership.business_id, ExpenseImport.user_id == user.id,
    ).order_by(ExpenseImport.created_at.desc()).limit(100).all()
    return [{"id": x.id, "status": x.status, "filename": x.filename, "total_rows": x.total_rows,
             "imported_rows": x.imported_rows, "invalid_rows": x.invalid_rows, "duplicate_rows": x.duplicate_rows,
             "created_at": x.created_at.isoformat(), "imported_at": x.imported_at.isoformat() if x.imported_at else None,
             "expires_at": x.expires_at.isoformat()} for x in imports]
