from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String, Index, func
from sqlalchemy.orm import relationship, validates

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email <> ''", name="ck_users_email_not_empty"),)

    id = Column(Integer, primary_key=True)
    email = Column(String(320), nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owned_businesses = relationship(
        "Business",
        back_populates="owner",
        foreign_keys="Business.owner_id",
        passive_deletes=True,
    )
    memberships = relationship(
        "BusinessMembership",
        back_populates="user",
        foreign_keys="BusinessMembership.user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @validates("email")
    def normalize_email(self, _key: str, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Email must be a string.")
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("Email must not be empty.")
        return normalized


Index("uq_users_email_normalized", func.lower(User.email), unique=True)
