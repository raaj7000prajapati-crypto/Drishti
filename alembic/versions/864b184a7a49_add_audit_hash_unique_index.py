"""add audit hash unique index

Revision ID: 864b184a7a49
Revises: 6a4a19387ba6
Create Date: 2026-10-31 19:19:06.335498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '864b184a7a49'
down_revision: Union[str, Sequence[str], None] = '6a4a19387ba6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("audit_logs")
    }
    if "uq_audit_logs_entry_hash" not in existing_indexes:
        op.create_index(
            "uq_audit_logs_entry_hash",
            "audit_logs",
            ["entry_hash"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("audit_logs")
    }
    if "uq_audit_logs_entry_hash" in existing_indexes:
        op.drop_index("uq_audit_logs_entry_hash", table_name="audit_logs")
