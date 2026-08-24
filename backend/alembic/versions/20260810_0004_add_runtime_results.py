"""add persisted Agent Runtime results

Revision ID: 20260810_0004
Revises: 20260806_0003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260810_0004"
down_revision = "20260806_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.String(100), nullable=False),
        sa.Column("tick_number", sa.BigInteger(), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("intent", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("result_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tick_number >= 0", name="ck_runtime_results_tick_number"),
        sa.CheckConstraint("retry_count >= 0", name="ck_runtime_results_retry_count"),
        sa.CheckConstraint(
            "status IN ('PROPOSED', 'FALLBACK', 'SKIPPED')",
            name="ck_runtime_results_status",
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_runtime_results_idempotency_key"),
        sa.UniqueConstraint(
            "run_id",
            "tick_number",
            "agent_id",
            name="uq_runtime_results_run_tick_agent",
        ),
    )
    op.create_index(
        "idx_runtime_results_run_tick",
        "runtime_results",
        ["run_id", "tick_number", "agent_id"],
    )
    op.create_index(
        "idx_runtime_results_run_failures",
        "runtime_results",
        ["run_id", "tick_number"],
        postgresql_where=sa.text("failure_reason IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_runtime_results_run_failures", table_name="runtime_results")
    op.drop_index("idx_runtime_results_run_tick", table_name="runtime_results")
    op.drop_table("runtime_results")
