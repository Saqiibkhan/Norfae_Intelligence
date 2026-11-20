"""Explicitly attach the confirmed legacy expense/settings rows to a provisioned business.

Run without --apply first. The script intentionally refuses to choose a business,
assign other table rows, or proceed when the audited legacy row counts changed.
"""

import argparse

from sqlalchemy import text

from app.core.database import engine


TENANT_TABLES = (
    "orders",
    "order_items",
    "products",
    "inventory_products",
    "meta_daily_stats",
    "creatives",
    "reports",
    "categories",
    "product_match_memory",
    "analytics",
)


def _preflight(connection, business_id: int) -> None:
    actual_businesses = connection.execute(
        text("SELECT count(*) FROM businesses")
    ).scalar_one()
    selected_business = connection.execute(
        text(
            "SELECT b.id FROM businesses b "
            "JOIN business_memberships m ON m.business_id = b.id "
            "WHERE b.id = :business_id AND b.is_active "
            "AND m.user_id = b.owner_id AND m.role = 'owner' AND m.is_active"
        ),
        {"business_id": business_id},
    ).scalar_one_or_none()
    if actual_businesses != 1 or selected_business != business_id:
        raise RuntimeError(
            "Backfill requires exactly one provisioned business with its active owner membership."
        )

    expense_count = connection.execute(text("SELECT count(*) FROM expenses")).scalar_one()
    settings_count = connection.execute(text("SELECT count(*) FROM settings")).scalar_one()
    if expense_count != 2 or settings_count != 1:
        raise RuntimeError(
            "Legacy expense/settings counts differ from the audited 2 and 1; stop for manual ownership review."
        )

    for table in ("expenses", "settings"):
        invalid = connection.execute(
            text(f"SELECT count(*) FROM {table} WHERE business_id IS NOT NULL AND business_id <> :business_id"),
            {"business_id": business_id},
        ).scalar_one()
        if invalid:
            raise RuntimeError(f"{table} already contains rows owned by another business.")

    for table in TENANT_TABLES:
        count = connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        if count:
            raise RuntimeError(
                f"{table} contains {count} rows; this script will not guess their ownership."
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true", help="Commit the two confirmed legacy assignments.")
    args = parser.parse_args()

    with engine.begin() as connection:
        _preflight(connection, args.business_id)
        if not args.apply:
            print("Preflight passed: exactly 2 expenses and 1 settings row can be assigned.")
            print("No rows changed. Re-run with --apply after reviewing this business ID.")
            return

        expenses_updated = connection.execute(
            text("UPDATE expenses SET business_id = :business_id WHERE business_id IS NULL"),
            {"business_id": args.business_id},
        ).rowcount
        settings_updated = connection.execute(
            text("UPDATE settings SET business_id = :business_id WHERE business_id IS NULL"),
            {"business_id": args.business_id},
        ).rowcount
        expense_total = connection.execute(text("SELECT count(*) FROM expenses")).scalar_one()
        expense_unassigned = connection.execute(
            text("SELECT count(*) FROM expenses WHERE business_id IS NULL")
        ).scalar_one()
        if expense_total != 2 or expense_unassigned != 0:
            raise RuntimeError("Expense row count changed unexpectedly; transaction rolled back.")
        expense_target_count = connection.execute(
            text("SELECT count(*) FROM expenses WHERE business_id = :business_id"),
            {"business_id": args.business_id},
        ).scalar_one()
        if expense_target_count != 2:
            raise RuntimeError("Not all expenses belong to the selected business; transaction rolled back.")
        settings_total = connection.execute(text("SELECT count(*) FROM settings")).scalar_one()
        settings_unassigned = connection.execute(
            text("SELECT count(*) FROM settings WHERE business_id IS NULL")
        ).scalar_one()
        if settings_total != 1 or settings_unassigned != 0:
            raise RuntimeError("Settings row count changed unexpectedly; transaction rolled back.")
        settings_target_count = connection.execute(
            text("SELECT count(*) FROM settings WHERE business_id = :business_id"),
            {"business_id": args.business_id},
        ).scalar_one()
        if settings_target_count != 1:
            raise RuntimeError("Settings do not belong to the selected business; transaction rolled back.")
        print(f"Assigned legacy rows: expenses={expenses_updated}, settings={settings_updated}.")


if __name__ == "__main__":
    main()
