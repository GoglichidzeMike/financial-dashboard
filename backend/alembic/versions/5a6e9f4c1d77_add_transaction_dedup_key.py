"""add transaction dedup key

Revision ID: 5a6e9f4c1d77
Revises: 2e7f9a1c4b22
Create Date: 2026-02-16 22:05:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5a6e9f4c1d77"
down_revision: Union[str, Sequence[str], None] = "2e7f9a1c4b22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.add_column("transactions", sa.Column("dedup_key", sa.String(length=64), nullable=True))

    op.execute(
        """
        UPDATE transactions
        SET dedup_key = encode(
            digest(
                CONCAT(
                    date::text,
                    '|',
                    to_char(amount_original::numeric, 'FM999999999999990.00'),
                    '|',
                    regexp_replace(lower(trim(description_raw)), '\\s+', ' ', 'g')
                ),
                'sha256'
            ),
            'hex'
        )
        WHERE dedup_key IS NULL
        """
    )

    op.alter_column("transactions", "dedup_key", nullable=False)
    op.create_index("uq_transactions_dedup_key", "transactions", ["dedup_key"], unique=True)
    op.create_index("idx_transactions_upload_id", "transactions", ["upload_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_transactions_upload_id", table_name="transactions")
    op.drop_index("uq_transactions_dedup_key", table_name="transactions")
    op.drop_column("transactions", "dedup_key")
