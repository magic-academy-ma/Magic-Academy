"""add share import idempotency ledger

Revision ID: 20260827_0011
Revises: 20260826_0010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260827_0011"
down_revision = "20260826_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("request_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("share_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["request_user_id"], ["users.id"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.ForeignKeyConstraint(["share_id"], ["simulation_shares.id"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.UniqueConstraint("request_user_id", "idempotency_key", name="uq_share_imports_user_key"),
    )


def downgrade() -> None:
    op.drop_table("share_imports")
