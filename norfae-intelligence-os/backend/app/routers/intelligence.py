from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.data_analysis import DataAnalysisInput
from app.agents.product_intelligence import ProductIntelligenceInput
from app.agents.city_intelligence import CityIntelligenceInput
from app.agents.marketing_intelligence import MarketingCampaignInput, MarketingInput
from app.agents.creative_intelligence import CreativeIntelligenceInput
from app.agents.intelligence_registry import intelligence_agents
from app.core.authorization import Permission, get_business_context
from app.core.dependencies import get_db
from app.models.business_membership_model import BusinessMembership
from app.schemas.intelligence_schema import (
    DataQualityReport,
    CityIntelligenceItem,
    CityIntelligenceLookup,
    CityIntelligencePage,
    OrderProfitability,
    ProductIntelligenceItem,
    ProductIntelligencePage,
    ProductProfitability,
    ProfitabilitySummary,
    MarketingOverview,
    MarketingCampaignPage,
    MarketingCampaignDetail,
    MarketingTrendResponse,
)
from app.schemas.creative_schema import (
    CreativeComparison,
    CreativeIntelligenceItem,
    CreativeIntelligencePage,
)
from app.schemas.anomaly_schema import (
    AnomalyCategory,
    AnomalyQuery,
    AnomalyRecord,
    AnomalyReport,
    AnomalySeverity,
    AnomalySummary,
)
from app.services.deterministic_profitability_service import DeterministicProfitabilityService
from app.services.product_intelligence_service import ProductIntelligenceService
from app.services.city_intelligence_service import CityIntelligenceService
from app.services.marketing_intelligence_service import MarketingIntelligenceService
from app.services.creative_intelligence_service import CreativeIntelligenceService
from app.services.anomaly_detection_service import AnomalyDetectionService

router = APIRouter(prefix="/intelligence", tags=["Business Intelligence"])
_data_analysis_agent = intelligence_agents.get_agent("data_analysis")
_product_intelligence_agent = intelligence_agents.get_agent("product_intelligence")
_city_intelligence_agent = intelligence_agents.get_agent("city_intelligence")
_marketing_overview_agent = intelligence_agents.get_agent("marketing_overview")
_marketing_campaign_agent = intelligence_agents.get_agent("marketing_campaigns")
_marketing_trends_agent = intelligence_agents.get_agent("marketing_trends")
_creative_intelligence_agent = intelligence_agents.get_agent("creative_intelligence")
_anomaly_detection_agent = intelligence_agents.get_agent("anomaly_detection")
_anomaly_detection_service = AnomalyDetectionService()


def _agent_context(membership: BusinessMembership, db: Session) -> AgentContext:
    return AgentContext(
        user_id=str(membership.user_id),
        business_id=str(membership.business_id),
        permissions=frozenset({Permission.ANALYTICS_READ.value}),
        dependencies={"db": db},
    )


@router.get("/data-quality", response_model=DataQualityReport)
async def analyze_data_quality(
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    return await _data_analysis_agent.execute(
        DataAnalysisInput(), context=_agent_context(membership, db)
    )


@router.get("/profitability", response_model=ProfitabilitySummary)
def get_profitability(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    try:
        return DeterministicProfitabilityService.overall(
            db, membership.business_id, start_date, end_date
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/profitability/products", response_model=list[ProductProfitability])
def get_product_profitability(
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    return DeterministicProfitabilityService.products(db, membership.business_id)


@router.get("/profitability/orders/{order_id}", response_model=OrderProfitability)
def get_order_profitability(
    order_id: int,
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    result = DeterministicProfitabilityService.order(db, membership.business_id, order_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return result


@router.get("/products", response_model=ProductIntelligencePage)
async def get_product_intelligence(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    payload = ProductIntelligenceInput(
        start_date=start_date, end_date=end_date, page=page, page_size=page_size
    )
    return await _product_intelligence_agent.execute(
        payload, context=_agent_context(membership, db)
    )


@router.get("/products/{product_id}", response_model=ProductIntelligenceItem)
def get_product_intelligence_detail(
    product_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    result = ProductIntelligenceService.get_product(
        db, membership.business_id, product_id, start_date, end_date
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return result


@router.get("/cities", response_model=CityIntelligencePage)
async def get_city_intelligence(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    payload = CityIntelligenceInput(start_date=start_date, end_date=end_date)
    return await _city_intelligence_agent.execute(
        payload, context=_agent_context(membership, db)
    )


@router.get("/cities/{city_name}", response_model=CityIntelligenceLookup)
def get_city_intelligence_detail(
    city_name: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    matches = CityIntelligenceService.get_city(
        db, membership.business_id, city_name, start_date, end_date
    )
    if not matches:
        raise HTTPException(status_code=404, detail="City not found.")
    return CityIntelligenceLookup(
        business_id=membership.business_id,
        requested_city=city_name,
        matches=matches,
    )


@router.get("/marketing/overview", response_model=MarketingOverview)
async def get_marketing_overview(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    return await _marketing_overview_agent.execute(
        MarketingInput(start_date=start_date, end_date=end_date),
        context=_agent_context(membership, db),
    )


@router.get("/marketing/campaigns", response_model=MarketingCampaignPage)
async def get_marketing_campaigns(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    level: str = Query(default="campaign", pattern="^(campaign|adset|ad)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    payload = MarketingCampaignInput(
        start_date=start_date, end_date=end_date, level=level,
        page=page, page_size=page_size,
    )
    return await _marketing_campaign_agent.execute(
        payload, context=_agent_context(membership, db)
    )


@router.get("/marketing/campaigns/{campaign_id}", response_model=MarketingCampaignDetail)
def get_marketing_campaign_detail(
    campaign_id: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    result = MarketingIntelligenceService.campaign_detail(
        db, membership.business_id, campaign_id, start_date, end_date
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return result


@router.get("/marketing/trends", response_model=MarketingTrendResponse)
async def get_marketing_trends(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    return await _marketing_trends_agent.execute(
        MarketingInput(start_date=start_date, end_date=end_date),
        context=_agent_context(membership, db),
    )


@router.get("/creatives", response_model=CreativeIntelligencePage)
async def get_creative_intelligence(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    return await _creative_intelligence_agent.execute(
        CreativeIntelligenceInput(
            start_date=start_date, end_date=end_date, page=page, page_size=page_size
        ),
        context=_agent_context(membership, db),
    )


@router.get("/creatives/comparison", response_model=CreativeComparison)
def compare_creatives(
    creative_ids: list[int] = Query(min_length=1, max_length=100),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    try:
        return CreativeIntelligenceService.compare(
            db, membership.business_id, creative_ids
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/creatives/{creative_id}", response_model=CreativeIntelligenceItem)
def get_creative_intelligence_detail(
    creative_id: int,
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    result = CreativeIntelligenceService.get_creative(
        db, membership.business_id, creative_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Creative not found.")
    return result


def _anomaly_query(
    start_date: date | None,
    end_date: date | None,
    category: AnomalyCategory | None,
    severity: AnomalySeverity | None,
    page: int,
    page_size: int,
) -> AnomalyQuery:
    return AnomalyQuery(
        start_date=start_date,
        end_date=end_date,
        category=category,
        severity=severity,
        page=page,
        page_size=page_size,
    )


def _anomaly_context(membership: BusinessMembership, db: Session) -> AgentContext:
    context = _agent_context(membership, db)
    return AgentContext(
        user_id=context.user_id,
        business_id=context.business_id,
        permissions=context.permissions,
        dependencies={
            "db": db,
            "anomaly_detection_service": _anomaly_detection_service,
        },
    )


@router.get("/anomalies", response_model=AnomalyReport)
async def get_anomalies(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category: AnomalyCategory | None = Query(default=None),
    severity: AnomalySeverity | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    try:
        payload = _anomaly_query(start_date, end_date, category, severity, page, page_size)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    return await _anomaly_detection_agent.execute(
        payload, context=_anomaly_context(membership, db)
    )


@router.get("/anomalies/summary", response_model=AnomalySummary)
def get_anomaly_summary(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category: AnomalyCategory | None = Query(default=None),
    severity: AnomalySeverity | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    try:
        payload = _anomaly_query(start_date, end_date, category, severity, 1, 50)
        return _anomaly_detection_service.summary(db, membership.business_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/anomalies/{anomaly_id}", response_model=AnomalyRecord)
def get_anomaly_detail(
    anomaly_id: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    category: AnomalyCategory | None = Query(default=None),
    severity: AnomalySeverity | None = Query(default=None),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(get_business_context),
):
    try:
        payload = _anomaly_query(start_date, end_date, category, severity, 1, 100)
        result = _anomaly_detection_service.get_anomaly(
            db, membership.business_id, anomaly_id, payload
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    if result is None:
        raise HTTPException(status_code=404, detail="Anomaly not found in the selected period.")
    return result
