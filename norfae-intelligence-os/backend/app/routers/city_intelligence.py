from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.services.city_intelligence_service import (
    CityIntelligenceService,
)

router = APIRouter(
    prefix="/city-intelligence",
    tags=["City Intelligence"],
)


@router.get("/")
def get_city_intelligence(
    db: Session = Depends(get_db),
):

    cities = CityIntelligenceService.get_city_intelligence(db)

    return {
        "success": True,
        "cities": cities,
    }
