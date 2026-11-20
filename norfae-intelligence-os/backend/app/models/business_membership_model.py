from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship, validates

from app.core.database import Base


class MembershipRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class BusinessMembership(Base):
    __tablename__ = "business_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "business_id", name="uq_business_memberships_user_business"
        ),
        CheckConstraint(
            "role IN ('owner', 'admin', 'analyst', 'viewer')",
            name="ck_business_memberships_role",
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id", name="fk_business_memberships_user_id_users", ondelete="CASCADE"
        ),
        nullable=False,
    )
    business_id = Column(
        Integer,
        ForeignKey(
            "businesses.id",
            name="fk_business_memberships_business_id_businesses",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    role = Column(
        SQLAlchemyEnum(
            MembershipRole,
            name="business_membership_role",
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=lambda roles: [role.value for role in roles],
            length=16,
        ),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship(
        "User", back_populates="memberships", foreign_keys=[user_id]
    )
    business = relationship(
        "Business", back_populates="memberships", foreign_keys=[business_id]
    )

    @validates("role")
    def validate_role(self, _key: str, value: MembershipRole | str) -> str:
        try:
            return MembershipRole(value).value
        except (TypeError, ValueError):
            allowed = ", ".join(role.value for role in MembershipRole)
            raise ValueError(f"Unsupported membership role. Choose one of: {allowed}.") from None
