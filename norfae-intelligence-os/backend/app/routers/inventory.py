from fastapi import APIRouter

from sqlalchemy.orm import Session

from app.core.database import SessionLocal

from app.services.inventory_import_service import (
    import_inventory_excel
)

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


@router.post("/import")
def import_inventory():

    db: Session = SessionLocal()

    result = import_inventory_excel(

        file_path="inventory.xlsx",

        db=db
    )

    return result