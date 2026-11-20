import math
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.creative_model import Creative
from app.schemas.creative_schema import (
    CreativeComparison,
    CreativeIntelligenceItem,
    CreativeIntelligencePage,
    CreativeRecordedMetric,
)


def _recorded(value, field_name: str) -> CreativeRecordedMetric:
    if value is None:
        return CreativeRecordedMetric(
            amount=None, available=False, note=f"{field_name} is not recorded."
        )
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return CreativeRecordedMetric(
            amount=None, available=False, note=f"{field_name} is not a valid number."
        )
    if not math.isfinite(number):
        return CreativeRecordedMetric(
            amount=None, available=False, note=f"{field_name} is not a finite number."
        )
    if number == 0:
        return CreativeRecordedMetric(
            amount=0.0,
            available=False,
            note=f"{field_name} is zero; the schema default makes zero observations indistinguishable from unreported values.",
        )
    return CreativeRecordedMetric(
        amount=number,
        available=True,
        note="Recorded on the legacy Creative row; source and reporting period are not tracked.",
    )


class CreativeIntelligenceService:
    """Read legacy creative records without treating them as Meta history."""

    @staticmethod
    def list_creatives(
        db: Session,
        business_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> CreativeIntelligencePage:
        if start_date and end_date and start_date > end_date:
            raise ValueError("start_date must be on or before end_date.")
        query = db.query(Creative).filter(Creative.business_id == business_id)
        if start_date:
            query = query.filter(Creative.created_at >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(
                Creative.created_at < datetime.combine(end_date + timedelta(days=1), time.min)
            )
        rows = query.order_by(Creative.id).all()
        items = [CreativeIntelligenceService._item(row) for row in rows]
        rankable = [item for item in items if item.recorded_roas.available]
        rankable.sort(key=lambda item: item.recorded_roas.amount)
        return CreativeIntelligencePage(
            business_id=business_id,
            start_date=start_date,
            end_date=end_date,
            total=len(items),
            page=page,
            page_size=page_size,
            best_recorded_roas_creative_id=rankable[-1].creative_id if rankable else None,
            lowest_recorded_roas_creative_id=rankable[0].creative_id if rankable else None,
            creatives=items[(page - 1) * page_size : page * page_size],
            warnings=[
                "The legacy Creative table has no Meta creative ID, ad/campaign link, metric date range, impressions, reach, clicks, conversions, frequency, or media asset.",
                "Metrics shown are recorded values, not verified Meta reports. Zero values are ambiguous because the columns default to zero.",
                "Date filters select record creation time, not the period represented by performance metrics.",
                "Best/lowest rankings compare only non-zero recorded ROAS values and are descriptive, not recommendations or causal conclusions.",
            ],
        )

    @staticmethod
    def _item(row: Creative) -> CreativeIntelligenceItem:
        return CreativeIntelligenceItem(
            creative_id=row.id,
            creative_name=row.creative_name,
            platform=row.platform,
            created_at=row.created_at,
            creative_type=None,
            campaign_id=None,
            campaign_name=None,
            ad_id=None,
            ad_name=None,
            spend=_recorded(row.spend, "Spend"),
            revenue=_recorded(row.revenue, "Revenue"),
            recorded_roas=_recorded(row.roas, "ROAS"),
            recorded_ctr=_recorded(row.ctr, "CTR"),
            recorded_cpc=_recorded(row.cpc, "CPC"),
            impressions=None,
            reach=None,
            clicks=None,
            frequency=None,
            reported_conversions=None,
            conversion_value=None,
            source="legacy creatives table",
        )

    @classmethod
    def get_creative(cls, db: Session, business_id: int, creative_id: int):
        row = (
            db.query(Creative)
            .filter(Creative.business_id == business_id, Creative.id == creative_id)
            .first()
        )
        return cls._item(row) if row else None

    @classmethod
    def compare(
        cls, db: Session, business_id: int, creative_ids: list[int]
    ) -> CreativeComparison:
        unique_ids = list(dict.fromkeys(creative_ids))
        if not unique_ids or len(unique_ids) > 100:
            raise ValueError("Provide between 1 and 100 creative IDs.")
        rows = (
            db.query(Creative)
            .filter(Creative.business_id == business_id, Creative.id.in_(unique_ids))
            .order_by(Creative.id)
            .all()
        )
        return CreativeComparison(
            business_id=business_id,
            requested_creative_ids=unique_ids,
            creatives=[cls._item(row) for row in rows],
            missing_creative_ids=sorted(set(unique_ids) - {row.id for row in rows}),
            warning="Comparison uses legacy recorded values with no source period; it is descriptive and may include default-zero placeholders.",
        )
