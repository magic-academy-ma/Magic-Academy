"""add user persona configuration and runtime execution metadata

Revision ID: 20260824_0006
Revises: 20260814_0005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260824_0006"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_persona_configs",
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mbti_type", sa.String(length=4), nullable=False),
        sa.Column("personality_rule_version", sa.String(length=50), nullable=False),
        sa.Column("openness", sa.SmallInteger(), nullable=False),
        sa.Column("conscientiousness", sa.SmallInteger(), nullable=False),
        sa.Column("extraversion", sa.SmallInteger(), nullable=False),
        sa.Column("agreeableness", sa.SmallInteger(), nullable=False),
        sa.Column("emotional_stability", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulations.id"],
            name="fk_user_persona_configs_simulation_id_simulations",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id", "agent_id"],
            ["agents.simulation_id", "agents.id"],
            name="fk_user_persona_configs_agent",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("simulation_id"),
        *[
            sa.CheckConstraint(
                f"{trait} BETWEEN -50 AND 50 AND {trait} % 5 = 0",
                name=f"ck_user_persona_configs_{trait}",
            )
            for trait in (
                "openness",
                "conscientiousness",
                "extraversion",
                "agreeableness",
                "emotional_stability",
            )
        ],
    )
    op.create_table(
        "runtime_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("tick_number", sa.BigInteger(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_version", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("seed >= 0", name="ck_runtime_executions_seed"),
        sa.CheckConstraint(
            "tick_number >= 0", name="ck_runtime_executions_tick_number"
        ),
        sa.ForeignKeyConstraint(
            ["simulation_id"],
            ["simulations.id"],
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_runtime_executions_run_id"),
        sa.UniqueConstraint(
            "simulation_id",
            "tick_number",
            name="uq_runtime_executions_simulation_tick",
        ),
    )
    op.create_index(
        "idx_runtime_executions_simulation_tick",
        "runtime_executions",
        ["simulation_id", sa.text("tick_number DESC")],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_runtime_executions_simulation_tick", table_name="runtime_executions"
    )
    op.drop_table("runtime_executions")
    op.drop_table("user_persona_configs")
