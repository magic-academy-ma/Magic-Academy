"""Add club challenge run persistence.

Revision ID: 20261010_0001
Revises: 20260828_0002
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261010_0001"
down_revision = "20260828_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "club_challenge_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "simulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("current_tick", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("member_count", sa.SmallInteger(), server_default="2", nullable=False),
        sa.Column("reputation", sa.SmallInteger(), server_default="40", nullable=False),
        sa.Column(
            "choices",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column("ending", sa.String(length=20), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("simulation_id", name="uq_club_challenge_runs_simulation"),
        sa.CheckConstraint("current_tick BETWEEN 0 AND 9", name="ck_club_challenge_runs_tick"),
        sa.CheckConstraint("member_count >= 0", name="ck_club_challenge_runs_members"),
        sa.CheckConstraint("reputation BETWEEN 0 AND 100", name="ck_club_challenge_runs_reputation"),
        sa.CheckConstraint("status IN ('in_progress', 'completed')", name="ck_club_challenge_runs_status"),
        sa.CheckConstraint(
            "ending IS NULL OR ending IN ('REVIVAL', 'CONDITIONAL', 'ONE_MEMBER', 'CLOSED')",
            name="ck_club_challenge_runs_ending",
        ),
    )


def downgrade():
    op.drop_table("club_challenge_runs")
