from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    owner_id = Column(
        Integer,
        ForeignKey("users.id", name="fk_businesses_owner_id_users"),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owner = relationship(
        "User", back_populates="owned_businesses", foreign_keys=[owner_id]
    )
    memberships = relationship(
        "BusinessMembership",
        back_populates="business",
        foreign_keys="BusinessMembership.business_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


Index("ix_businesses_owner_id", Business.owner_id)
