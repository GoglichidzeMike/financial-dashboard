"""add upload job fields

Revision ID: 9c1f7d3a4b11
Revises: 5a6e9f4c1d77
Create Date: 2026-02-18 00:05:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c1f7d3a4b11"
down_revision: Union[str, Sequence[str], None] = "5a6e9f4c1d77"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("uploads", sa.Column("rows_total", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("rows_skipped_non_transaction", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("rows_invalid", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("rows_duplicate", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("llm_used_count", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("fallback_used_count", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("embeddings_generated", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("error_message", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("uploads", "error_message")
    op.drop_column("uploads", "embeddings_generated")
    op.drop_column("uploads", "fallback_used_count")
    op.drop_column("uploads", "llm_used_count")
    op.drop_column("uploads", "rows_duplicate")
    op.drop_column("uploads", "rows_invalid")
    op.drop_column("uploads", "rows_skipped_non_transaction")
    op.drop_column("uploads", "rows_total")
