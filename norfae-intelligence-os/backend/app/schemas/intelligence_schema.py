from datetime import date, datetime

from pydantic import BaseModel


class DataQualityIssue(BaseModel):
    record_type: str
    record_id: int | None = None
    code: str
    field: str | None = None
    message: str
    suggested_value: str | None = None


class NormalizationPreview(BaseModel):
    record_type: str
    record_id: int
    normalized_fields: dict[str, str]


class DataQualityReport(BaseModel):
    business_id: int
    generated_at: datetime
    total_records_inspected: int
    valid_records: int
    invalid_records: int
    missing_fields: dict[str, int]
    duplicate_records: dict[str, int]
    warnings: list[str]
    recommended_corrections: list[str]
    normalization_preview: list[NormalizationPreview]
    issues: list[DataQualityIssue]


class ProfitabilityComponent(BaseModel):
    amount: float | None
    available: bool
    source: str | None = None
    note: str | None = None


class ProfitabilitySummary(BaseModel):
    business_id: int
    start_date: date | None = None
    end_date: date | None = None
    orders_inspected: int
    delivered_orders: int
    cancelled_orders: int
    returned_orders: int
    other_status_orders: int
    gross_revenue: ProfitabilityComponent
    discounts: ProfitabilityComponent
    refunds: ProfitabilityComponent
    net_revenue: ProfitabilityComponent
    cost_of_goods_sold: ProfitabilityComponent
    packaging_cost: ProfitabilityComponent
    delivery_cost: ProfitabilityComponent
    advertising_expense: ProfitabilityComponent
    other_business_expenses: ProfitabilityComponent
    net_profit: ProfitabilityComponent
    profit_margin_percent: float | None
    complete: bool
    warnings: list[str]


class ProductProfitability(BaseModel):
    product_key: str
    product_name: str | None
    sku: str | None
    units_sold: int
    revenue: ProfitabilityComponent
    cost_of_goods_sold: ProfitabilityComponent
    contribution_profit: ProfitabilityComponent
    contribution_margin_percent: float | None
    complete: bool
    warnings: list[str]


class OrderProfitability(BaseModel):
    order_id: int
    status: str | None
    revenue: ProfitabilityComponent
    discounts: ProfitabilityComponent
    refunds: ProfitabilityComponent
    cost_of_goods_sold: ProfitabilityComponent
    packaging_cost: ProfitabilityComponent
    delivery_cost: ProfitabilityComponent
    advertising_cost: ProfitabilityComponent
    other_order_costs: ProfitabilityComponent
    net_profit: ProfitabilityComponent
    profit_margin_percent: float | None
    complete: bool
    warnings: list[str]


class ProductIntelligenceItem(BaseModel):
    product_id: int
    name: str
    sku: str | None
    total_units_sold: int
    order_count: int
    delivered_orders: int
    cancelled_orders: int
    returned_orders: int
    cancellation_rate_percent: float | None
    return_rate_percent: float | None
    revenue: ProfitabilityComponent
    recorded_product_cost: ProfitabilityComponent
    product_contribution: ProfitabilityComponent
    contribution_margin_percent: float | None
    average_selling_price: float | None
    previous_period_revenue_change_percent: float | None
    unusual_performance_change: bool
    performance_status: str
    fully_allocated_business_profit: ProfitabilityComponent
    recommendations: list[str]
    warnings: list[str]


class ProductIntelligencePage(BaseModel):
    business_id: int
    start_date: date | None
    end_date: date | None
    total_products: int
    page: int
    page_size: int
    best_performing_product_id: int | None
    lowest_performing_product_id: int | None
    products: list[ProductIntelligenceItem]
    warnings: list[str]


class CityIntelligenceItem(BaseModel):
    city: str | None
    province: str | None
    total_orders: int
    delivered_orders: int
    cancelled_orders: int
    returned_orders: int
    cancellation_rate_percent: float | None
    return_rate_percent: float | None
    total_revenue: ProfitabilityComponent
    average_order_value: float | None
    recorded_delivery_costs: ProfitabilityComponent
    delivery_cost_per_delivered_order: float | None
    product_contribution: ProfitabilityComponent
    contribution_margin_percent: float | None
    estimated_order_profit: ProfitabilityComponent
    unallocated_business_expenses: ProfitabilityComponent
    previous_period_revenue_change_percent: float | None
    unusual_performance_change: bool
    recommendations: list[str]
    warnings: list[str]


class CityIntelligencePage(BaseModel):
    business_id: int
    start_date: date | None
    end_date: date | None
    total_cities: int
    best_performing_city: str | None
    lowest_performing_city: str | None
    cities: list[CityIntelligenceItem]
    warnings: list[str]


class CityIntelligenceLookup(BaseModel):
    business_id: int
    requested_city: str
    matches: list[CityIntelligenceItem]


class MarketingMetric(BaseModel):
    amount: float | None
    available: bool
    source: str | None = None
    note: str | None = None


class MarketingOverview(BaseModel):
    business_id: int
    start_date: date | None
    end_date: date | None
    spend: MarketingMetric
    meta_expense_ledger_spend: MarketingMetric
    other_marketing_expenses: MarketingMetric
    meta_ledger_overlap_amount: MarketingMetric
    overlap_days: int
    impressions: MarketingMetric
    reach: MarketingMetric
    clicks: MarketingMetric
    link_clicks: MarketingMetric
    leads: MarketingMetric
    instagram_messages: MarketingMetric
    attributed_purchase_count: MarketingMetric
    attributed_conversion_value: MarketingMetric
    observed_business_revenue: MarketingMetric
    observed_business_profit_estimate: MarketingMetric
    observed_revenue_attribution_note: str
    ctr_percent: float | None
    cpc: float | None
    cpm: float | None
    cpa: float | None
    roas: float | None
    warnings: list[str]


class MarketingEntityPerformance(BaseModel):
    level: str
    entity_id: str
    entity_name: str | None
    campaign_id: str | None
    campaign_name: str | None
    adset_id: str | None = None
    adset_name: str | None = None
    ad_id: str | None = None
    ad_name: str | None = None
    spend: MarketingMetric
    impressions: MarketingMetric
    reach: MarketingMetric
    clicks: MarketingMetric
    link_clicks: MarketingMetric
    attributed_purchase_count: MarketingMetric
    attributed_conversion_value: MarketingMetric
    leads: MarketingMetric
    instagram_messages: MarketingMetric
    ctr_percent: float | None
    cpc: float | None
    cpm: float | None
    cpa: float | None
    roas: float | None
    previous_spend_change_percent: float | None
    previous_ctr_change_percent: float | None
    unusual_spend_change: bool
    sufficient_data_for_conclusions: bool
    recommendations: list[str]
    warnings: list[str]


class MarketingCampaignPage(BaseModel):
    business_id: int
    level: str
    start_date: date | None
    end_date: date | None
    total: int
    page: int
    page_size: int
    best_performing_entity_id: str | None
    worst_performing_entity_id: str | None
    campaigns: list[MarketingEntityPerformance]
    warnings: list[str]


class MarketingCampaignDetail(BaseModel):
    business_id: int
    campaign: MarketingEntityPerformance
    adsets: list[MarketingEntityPerformance]
    ads: list[MarketingEntityPerformance]
    warnings: list[str]


class MarketingTrendPoint(BaseModel):
    stats_date: date
    spend: MarketingMetric
    impressions: MarketingMetric
    clicks: MarketingMetric
    ctr_percent: float | None
    cpc: float | None
    cpm: float | None


class MarketingTrendResponse(BaseModel):
    business_id: int
    start_date: date | None
    end_date: date | None
    points: list[MarketingTrendPoint]
    warnings: list[str]
