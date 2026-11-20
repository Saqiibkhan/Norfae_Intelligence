from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_db

from app.models.category_model import Category

router = APIRouter(
    prefix="/categories",
    tags=["Categories"],
)

# ===================================
# GET ALL CATEGORIES
# ===================================


@router.get("/")
def get_categories(db: Session = Depends(get_db)):

    categories = db.query(Category).order_by(Category.name).all()

    return categories


# ===================================
# CREATE CATEGORY
# ===================================


@router.post("/")
def create_category(
    name: str,
    db: Session = Depends(get_db),
):

    existing = db.query(Category).filter(Category.name == name).first()

    if existing:

        return {
            "success": False,
            "message": "Category already exists",
        }

    category = Category(
        name=name,
        slug=name.lower().replace(" ", "-"),
    )

    db.add(category)

    db.commit()

    db.refresh(category)

    return {
        "success": True,
        "category": category,
    }
