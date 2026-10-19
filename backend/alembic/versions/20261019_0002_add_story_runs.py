"""Add story mode runs and CHAPTER 2/4 run state.

Revision ID: 20261019_0002
Revises: 20261019_0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261019_0002"
down_revision = "20261019_0001"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade():
    op.create_table(
        "story_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chapter", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("chapter_run_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("records", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("final_ending", sa.String(10)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("chapter BETWEEN 1 AND 5", name="ck_story_runs_chapter"),
        sa.CheckConstraint("status IN ('in_progress', 'completed')", name="ck_story_runs_status"),
        sa.CheckConstraint(
            "final_ending IS NULL OR final_ending IN ('BEST', 'NORMAL', 'BAD')",
            name="ck_story_runs_final_ending",
        ),
    )
    op.create_index("idx_story_runs_owner_created", "story_runs", ["owner_id", sa.text("created_at DESC")])
    op.create_table(
        "story_chapter_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "simulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("chapter", sa.SmallInteger(), nullable=False),
        sa.Column("seed", sa.BigInteger(), nullable=False),
        sa.Column("current_tick", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("state", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("interventions", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
        sa.Column("ending", sa.String(20)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.UniqueConstraint("simulation_id", name="uq_story_chapter_runs_simulation"),
        sa.CheckConstraint("chapter IN (2, 4)", name="ck_story_chapter_runs_chapter"),
        sa.CheckConstraint("current_tick BETWEEN 0 AND 9", name="ck_story_chapter_runs_tick"),
        sa.CheckConstraint("status IN ('in_progress', 'completed')", name="ck_story_chapter_runs_status"),
    )


def downgrade():
    op.drop_table("story_chapter_runs")
    op.drop_index("idx_story_runs_owner_created", table_name="story_runs")
    op.drop_table("story_runs")
