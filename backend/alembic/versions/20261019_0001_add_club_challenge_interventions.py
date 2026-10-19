"""Add club challenge intervention records.

Revision ID: 20261019_0001
Revises: 20261017_0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20261019_0001"
down_revision = "20261017_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "club_challenge_runs",
        sa.Column(
            "interventions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade():
    op.drop_column("club_challenge_runs", "interventions")
