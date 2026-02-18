"""add chat persistence tables

Revision ID: b81e2cd9a743
Revises: cf7b3a9d1122
Create Date: 2026-02-17 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b81e2cd9a743"
down_revision: Union[str, None] = "cf7b3a9d1122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "chat_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "chat_threads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("chat_profiles.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "idx_chat_threads_profile_updated",
        "chat_threads",
        ["profile_id", "updated_at"],
    )
    op.create_index(
        "idx_chat_threads_profile_status_updated",
        "chat_threads",
        ["profile_id", "status", "updated_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("question_text", sa.Text()),
        sa.Column("answer_text", sa.Text()),
        sa.Column("mode", sa.Text()),
        sa.Column("sources_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("filters_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("meta_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "idx_chat_messages_thread_created",
        "chat_messages",
        ["thread_id", "created_at"],
    )
    op.create_index(
        "idx_chat_messages_thread_role_created",
        "chat_messages",
        ["thread_id", "role", "created_at"],
    )

    op.execute(
        """
        INSERT INTO chat_profiles (slug, display_name)
        VALUES ('default', 'Local User')
        ON CONFLICT (slug) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("idx_chat_messages_thread_role_created", table_name="chat_messages")
    op.drop_index("idx_chat_messages_thread_created", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("idx_chat_threads_profile_status_updated", table_name="chat_threads")
    op.drop_index("idx_chat_threads_profile_updated", table_name="chat_threads")
    op.drop_table("chat_threads")

    op.drop_table("chat_profiles")
