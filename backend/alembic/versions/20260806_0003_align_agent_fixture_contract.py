"""align databases created before the DB v1 review fixes

Revision ID: 20260806_0003
Revises: 20260805_0002

Fresh databases already receive this schema from 0001. This compatibility
revision only upgrades databases that applied the earlier 0001/0002 pair.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260806_0003"
down_revision = "20260805_0002"
branch_labels = None
depends_on = None


BIG_FIVE_COLUMNS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "emotional_stability",
)


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        constraint["name"]
        for constraint in inspector.get_check_constraints(table_name)
        if constraint["name"]
    }


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    agent_columns = _column_names(inspector, "agents")

    if "fixture_key" not in agent_columns:
        op.add_column("agents", sa.Column("fixture_key", sa.String(50), nullable=True))
        op.add_column("agents", sa.Column("fixture_version", sa.String(50), nullable=True))
        op.create_unique_constraint(
            "uq_agents_simulation_fixture_key",
            "agents",
            ["simulation_id", "fixture_key"],
        )

    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM agents "
            "WHERE fixture_key IS NULL OR fixture_version IS NULL)"
        )
    ).scalar():
        raise RuntimeError("agents fixture_key and fixture_version require an explicit backfill")

    op.alter_column("agents", "fixture_key", existing_type=sa.String(50), nullable=False)
    op.alter_column("agents", "fixture_version", existing_type=sa.String(50), nullable=False)

    invalid_big_five = " OR ".join(
        f"{column} NOT BETWEEN -50 AND 50 OR {column} % 5 <> 0"
        for column in BIG_FIVE_COLUMNS
    )
    if connection.execute(
        sa.text(f"SELECT EXISTS (SELECT 1 FROM agents WHERE {invalid_big_five})")
    ).scalar():
        raise RuntimeError("agent Big Five values require an explicit signed-scale backfill")

    check_constraints = _constraint_names(sa.inspect(connection), "agents")
    for column in BIG_FIVE_COLUMNS:
        constraint_name = f"ck_agents_{column}"
        if constraint_name in check_constraints:
            op.drop_constraint(constraint_name, "agents", type_="check")
        op.create_check_constraint(
            constraint_name,
            "agents",
            f"{column} BETWEEN -50 AND 50 AND {column} % 5 = 0",
        )
        op.alter_column(
            "agents",
            column,
            existing_type=sa.SmallInteger(),
            server_default=sa.text("0"),
        )

    existing_tables = set(sa.inspect(connection).get_table_names())
    if "student_profiles" not in existing_tables:
        op.create_table(
            "student_profiles",
            sa.Column(
                "agent_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
                primary_key=True,
            ),
            sa.Column("grade", sa.SmallInteger(), nullable=False),
            sa.Column("interest_field", sa.String(100), nullable=False),
            sa.CheckConstraint("grade BETWEEN 1 AND 4", name="ck_student_profiles_grade"),
        )
    if "professor_profiles" not in existing_tables:
        op.create_table(
            "professor_profiles",
            sa.Column(
                "agent_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
                primary_key=True,
            ),
            sa.Column("academic_rank", sa.String(50), nullable=False),
            sa.Column("specialty", sa.String(200), nullable=False),
        )

    if "grade" in agent_columns:
        op.drop_constraint("ck_agents_grade", "agents", type_="check")
        op.drop_column("agents", "grade")


def downgrade() -> None:
    # 0001 owns the reviewed DB v1 schema. Reversing this compatibility shim
    # must not remove tables or constraints that fresh databases got from 0001.
    pass
