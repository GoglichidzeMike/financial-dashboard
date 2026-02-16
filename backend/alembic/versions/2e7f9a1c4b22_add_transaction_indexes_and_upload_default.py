"""add transaction indexes and upload status default

Revision ID: 2e7f9a1c4b22
Revises: 75c8f1d32685
Create Date: 2026-02-16 21:15:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2e7f9a1c4b22"
down_revision: Union[str, Sequence[str], None] = "75c8f1d32685"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_transactions_date", "transactions", ["date"], unique=False)
    op.create_index(
        "idx_transactions_merchant", "transactions", ["merchant_id"], unique=False
    )
    op.execute(
        "CREATE INDEX idx_transactions_embedding ON transactions "
        "USING ivfflat (embedding vector_cosine_ops)"
    )
    op.alter_column(
        "uploads",
        "status",
        existing_type=sa.String(),
        nullable=False,
        server_default=sa.text("'processing'"),
    )


def downgrade() -> None:
    op.alter_column(
        "uploads",
        "status",
        existing_type=sa.String(),
        nullable=False,
        server_default=None,
    )
    op.drop_index("idx_transactions_embedding", table_name="transactions")
    op.drop_index("idx_transactions_merchant", table_name="transactions")
    op.drop_index("idx_transactions_date", table_name="transactions")
