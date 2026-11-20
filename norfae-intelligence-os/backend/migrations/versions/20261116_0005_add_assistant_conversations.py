"""add tenant-scoped assistant conversations

Revision ID: 20261116_0005
Revises: 20261116_0004
Create Date: 2026-11-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261116_0005"
down_revision: Union[str, None] = "20261116_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_assistant_conversations_business_id", "assistant_conversations", ["business_id"])
    op.create_index("ix_assistant_conversations_user_id", "assistant_conversations", ["user_id"])
    op.create_index("ix_assistant_conversations_updated_at", "assistant_conversations", ["updated_at"])
    op.create_index("ix_assistant_conversations_business_user_updated", "assistant_conversations", ["business_id", "user_id", "updated_at"])
    op.create_unique_constraint(
        "uq_assistant_conversations_business_id_id",
        "assistant_conversations",
        ["business_id", "id"],
    )
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.String(length=12000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id", "conversation_id"],
            ["assistant_conversations.business_id", "assistant_conversations.id"],
            ondelete="CASCADE",
            name="fk_assistant_messages_business_conversation",
        ),
    )
    op.create_index("ix_assistant_messages_business_id", "assistant_messages", ["business_id"])
    op.create_index("ix_assistant_messages_conversation_id", "assistant_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("assistant_messages")
    op.drop_table("assistant_conversations")
