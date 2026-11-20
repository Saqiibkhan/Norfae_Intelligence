from app.agents.city_intelligence import CityIntelligenceAgent
from app.agents.data_analysis import DataAnalysisAgent
from app.agents.product_intelligence import ProductIntelligenceAgent
from app.agents.creative_intelligence import CreativeIntelligenceAgent
from app.agents.anomaly_detection import AnomalyDetectionAgent
from app.agents.business_assistant import BusinessAssistantAgent
from app.agents.marketing_intelligence import (
    MarketingCampaignAgent,
    MarketingOverviewAgent,
    MarketingTrendsAgent,
)
from app.agents.registry import AgentRegistry


intelligence_agents = AgentRegistry()
for _agent in (
    DataAnalysisAgent(),
    ProductIntelligenceAgent(),
    CityIntelligenceAgent(),
    MarketingOverviewAgent(),
    MarketingCampaignAgent(),
    MarketingTrendsAgent(),
    CreativeIntelligenceAgent(),
    AnomalyDetectionAgent(),
    BusinessAssistantAgent(),
):
    intelligence_agents.register(_agent)
