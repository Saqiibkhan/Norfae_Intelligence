from fastapi import APIRouter

from app.services.creative_analysis_service import (
    CreativeAnalysisService
)

router = APIRouter(
    prefix="/creatives",
    tags=["Creatives"]
)


@router.get("/analyze")
def analyze_creative(
    ctr: float,
    roas: float,
    spend: float
):

    return (
        CreativeAnalysisService
        .analyze_creative(
            ctr,
            roas,
            spend
        )
    )