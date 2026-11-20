from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base


class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"
    __table_args__ = (UniqueConstraint("business_id", "id", name="uq_assistant_conversations_business_id_id"),)

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    messages = relationship("AssistantMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="AssistantMessage.id")


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "conversation_id"],
            ["assistant_conversations.business_id", "assistant_conversations.id"],
            ondelete="CASCADE",
            name="fk_assistant_messages_business_conversation",
        ),
    )

    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, nullable=False, index=True)
    role = Column(String(16), nullable=False)
    content = Column(String(12000), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    conversation = relationship("AssistantConversation", back_populates="messages")


Index("ix_assistant_conversations_business_user_updated", AssistantConversation.business_id, AssistantConversation.user_id, AssistantConversation.updated_at)
