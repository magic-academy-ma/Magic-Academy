"""allow runtime execution metadata without an applied policy

Revision ID: 20260824_0007
Revises: 20260824_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20260824_0007"
down_revision = "20260824_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "runtime_executions",
        "policy_version",
        existing_type=sa.String(length=100),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE runtime_executions "
        "SET policy_version = 'policy-unapplied' "
        "WHERE policy_version IS NULL"
    )
    op.alter_column(
        "runtime_executions",
        "policy_version",
        existing_type=sa.String(length=100),
        nullable=False,
    )
