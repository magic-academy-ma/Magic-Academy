"""add Slice 0 authentication and fixture ownership

Revision ID: 20260805_0002
Revises: 20260805_0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260805_0002"
down_revision = "20260805_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT EXISTS (SELECT 1 FROM simulations)")).scalar():
        raise RuntimeError("simulations.owner_id requires an explicit backfill for existing rows")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("roles", postgresql.JSONB(), nullable=False, server_default=sa.text("'[\"USER\"]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.add_column("simulations", sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False))
    op.create_foreign_key("fk_simulations_owner", "simulations", "users", ["owner_id"], ["id"], ondelete="RESTRICT", onupdate="RESTRICT")
    op.create_index("idx_simulations_owner_created", "simulations", ["owner_id", sa.text("created_at DESC")])

    op.add_column("agents", sa.Column("fixture_key", sa.String(50), nullable=True))
    op.add_column("agents", sa.Column("fixture_version", sa.String(50), nullable=True))
    op.add_column("agents", sa.Column("grade", sa.SmallInteger(), nullable=True))
    op.create_unique_constraint("uq_agents_simulation_fixture_key", "agents", ["simulation_id", "fixture_key"])
    op.create_check_constraint("ck_agents_grade", "agents", "grade IS NULL OR grade BETWEEN 1 AND 4")


def downgrade() -> None:
    op.drop_constraint("ck_agents_grade", "agents", type_="check")
    op.drop_constraint("uq_agents_simulation_fixture_key", "agents", type_="unique")
    op.drop_column("agents", "grade")
    op.drop_column("agents", "fixture_version")
    op.drop_column("agents", "fixture_key")
    op.drop_index("idx_simulations_owner_created", table_name="simulations")
    op.drop_constraint("fk_simulations_owner", "simulations", type_="foreignkey")
    op.drop_column("simulations", "owner_id")
    op.drop_table("users")
