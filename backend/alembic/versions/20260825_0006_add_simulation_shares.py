"""add shared simulation records

Revision ID: 20260825_0006
Revises: 20260814_0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260825_0006"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="private"),
        sa.Column("export_schema_version", sa.String(30), nullable=False, server_default="slice7-share-v1"),
        sa.Column(
            "export_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT", onupdate="RESTRICT"),
        sa.CheckConstraint("visibility IN ('private', 'unlisted', 'public')", name="ck_simulation_shares_visibility"),
    )
    # Only one *active* (non-revoked) share per Simulation. Revoked shares do not
    # block re-sharing the same Simulation with a new share record.
    op.create_index(
        "uq_simulation_shares_active_simulation",
        "simulation_shares",
        ["simulation_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    op.create_index(
        "idx_simulation_shares_public_listing",
        "simulation_shares",
        ["visibility", "created_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_simulation_shares_public_listing", table_name="simulation_shares")
    op.drop_index("uq_simulation_shares_active_simulation", table_name="simulation_shares")
    op.drop_table("simulation_shares")
