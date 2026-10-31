"""add similarity metadata and thresholds

Revision ID: 6a4a19387ba6
Revises: 8dde965677c8
Create Date: 2026-10-31 18:43:27.929007

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a4a19387ba6'
down_revision: Union[str, Sequence[str], None] = '8dde965677c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "similarity_threshold_config" not in inspector.get_table_names():
        op.create_table(
            "similarity_threshold_config",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("high_threshold", sa.Float(), nullable=False),
            sa.Column("medium_threshold", sa.Float(), nullable=False),
            sa.Column("low_threshold", sa.Float(), nullable=False),
            sa.Column("updated_by_id", sa.Integer(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["updated_by_id"], ["users.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    case_link_columns = {
        column["name"] for column in inspector.get_columns("case_links")
    }
    if "shared_metadata" not in case_link_columns:
        op.add_column(
            "case_links", sa.Column("shared_metadata", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "shared_metadata" in {
        column["name"] for column in inspector.get_columns("case_links")
    }:
        op.drop_column("case_links", "shared_metadata")
    if "similarity_threshold_config" in inspector.get_table_names():
        op.drop_table("similarity_threshold_config")
