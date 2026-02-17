"""add upload progress fields

Revision ID: cf7b3a9d1122
Revises: 9c1f7d3a4b11
Create Date: 2026-02-18 00:45:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "cf7b3a9d1122"
down_revision: Union[str, Sequence[str], None] = "9c1f7d3a4b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("uploads", sa.Column("rows_processed", sa.Integer(), nullable=True))
    op.add_column("uploads", sa.Column("processing_phase", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("uploads", "processing_phase")
    op.drop_column("uploads", "rows_processed")
