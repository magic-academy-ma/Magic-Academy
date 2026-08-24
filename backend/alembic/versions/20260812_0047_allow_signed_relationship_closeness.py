"""allow signed relationship closeness values

Revision ID: 20260812_0047
Revises: 20260814_0005
"""

from alembic import op
import sqlalchemy as sa


revision = "20260812_0047"
down_revision = "20260814_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_relationships_closeness",
        "relationships",
        type_="check",
    )
    op.create_check_constraint(
        "ck_relationships_closeness",
        "relationships",
        "closeness BETWEEN -100 AND 100",
    )


def downgrade() -> None:
    connection = op.get_bind()
    has_negative_closeness = connection.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM relationships WHERE closeness < 0)")
    ).scalar()
    if has_negative_closeness:
        raise RuntimeError(
            "negative relationship closeness values require an explicit backfill"
        )

    op.drop_constraint(
        "ck_relationships_closeness",
        "relationships",
        type_="check",
    )
    op.create_check_constraint(
        "ck_relationships_closeness",
        "relationships",
        "closeness BETWEEN 0 AND 100",
    )
