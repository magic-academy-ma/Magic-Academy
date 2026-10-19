"""Add per-account achievements.

Revision ID: 20261019_0003
Revises: 20261019_0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261019_0003"
down_revision = "20261019_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_achievements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("achievement_id", sa.String(40), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "achievement_id", name="uq_user_achievements_user_achievement"),
    )


def downgrade():
    op.drop_table("user_achievements")
