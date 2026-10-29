"""Add club challenge initial member affections.

Revision ID: 20261019_0004
Revises: 20261019_0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261019_0004"
down_revision = "20261019_0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "club_challenge_runs",
        sa.Column(
            "initial_member_affections",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade():
    op.drop_column("club_challenge_runs", "initial_member_affections")
