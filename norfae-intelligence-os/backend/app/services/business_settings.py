from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import get_current_business_id
from app.models.settings_model import SettingsModel


class LegacySettingsNotBackfilled(RuntimeError):
    """The confirmed legacy global settings row has not been assigned yet."""


def get_or_create_business_settings(db: Session) -> SettingsModel:
    business_id = get_current_business_id()
    if business_id is None:
        raise RuntimeError("Business settings require an authorized business context.")

    settings = db.query(SettingsModel).first()
    if settings is not None:
        return settings

    # This Core query deliberately checks only whether the audited legacy row
    # remains unassigned. It never reads or returns the row's credentials.
    settings_table = SettingsModel.__table__
    legacy_row_id = db.execute(
        select(settings_table.c.id)
        .where(settings_table.c.business_id.is_(None))
        .limit(1)
    ).scalar_one_or_none()
    if legacy_row_id is not None:
        raise LegacySettingsNotBackfilled(
            "The confirmed legacy settings row must be backfilled before creating business settings."
        )

    settings = SettingsModel(business_id=business_id)
    db.add(settings)
    db.flush()
    return settings
