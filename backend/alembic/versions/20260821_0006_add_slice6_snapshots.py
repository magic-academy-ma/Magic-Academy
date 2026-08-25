"""add Slice 6 versioned settings and immutable snapshots

Revision ID: 20260821_0006
Revises: 20260814_0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260821_0006"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("event_frequency", sa.String(10), nullable=False),
        sa.Column("event_impact", sa.String(10), nullable=False),
        sa.Column("magic_enabled", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(100)),
        sa.Column("resolver_version", sa.String(100)),
        sa.Column("user_persona_settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("simulation_id", "version", name="uq_simulation_configs_version"),
        sa.CheckConstraint("version >= 1", name="ck_simulation_configs_version"),
        sa.CheckConstraint("event_frequency IN ('low', 'medium', 'high')", name="ck_simulation_configs_event_frequency"),
        sa.CheckConstraint("event_impact IN ('low', 'medium', 'high')", name="ck_simulation_configs_event_impact"),
    )
    op.create_table(
        "simulation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tick_number", sa.BigInteger(), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["simulation_id"], ["simulations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["simulation_id", "config_version"],
            ["simulation_configs.simulation_id", "simulation_configs.version"],
            name="fk_simulation_snapshots_config",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("simulation_id", "tick_number", name="uq_simulation_snapshots_tick"),
        sa.CheckConstraint("tick_number >= 0", name="ck_simulation_snapshots_tick"),
        sa.CheckConstraint("config_version >= 1", name="ck_simulation_snapshots_config_version"),
    )
    op.create_index("idx_simulation_snapshots_timeline", "simulation_snapshots", ["simulation_id", "tick_number"])


def downgrade() -> None:
    op.drop_index("idx_simulation_snapshots_timeline", table_name="simulation_snapshots")
    op.drop_table("simulation_snapshots")
    op.drop_table("simulation_configs")
