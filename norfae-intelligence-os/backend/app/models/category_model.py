from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, UniqueConstraint
from app.core.database import Base


class Category(Base):

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("business_id", "name", name="uq_categories_business_name"),
        UniqueConstraint("business_id", "slug", name="uq_categories_business_slug"),
    )

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String)

    slug = Column(String)

    is_active = Column(Boolean, default=True)
