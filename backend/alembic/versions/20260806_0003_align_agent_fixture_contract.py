"""align Agent fixtures and role profiles

Revision ID: 20260806_0003
Revises: 20260805_0002
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


def upgrade() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM agents "
            "WHERE fixture_key IS NULL OR fixture_version IS NULL)"
        )
    ).scalar():
        raise RuntimeError("agents fixture_key and fixture_version require an explicit backfill")

    op.alter_column("agents", "fixture_key", existing_type=sa.String(50), nullable=False)
    op.alter_column("agents", "fixture_version", existing_type=sa.String(50), nullable=False)

    for column in BIG_FIVE_COLUMNS:
        op.drop_constraint(f"ck_agents_{column}", "agents", type_="check")
        op.create_check_constraint(
            f"ck_agents_{column}",
            "agents",
            f"{column} BETWEEN -50 AND 50 AND {column} % 5 = 0",
        )
        op.alter_column(
            "agents",
            column,
            existing_type=sa.SmallInteger(),
            server_default=sa.text("0"),
        )

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

    connection.execute(
        sa.text(
            """
            INSERT INTO student_profiles (agent_id, grade, interest_field)
            SELECT id,
                   grade,
                   CASE fixture_key
                     WHEN 'student-01' THEN '방어 마법'
                     WHEN 'student-02' THEN '마법 생물'
                     WHEN 'student-03' THEN '고대 마법'
                     WHEN 'student-04' THEN '마법 도구 제작'
                     WHEN 'student-05' THEN '마법약'
                   END
            FROM agents
            WHERE fixture_key IN ('student-01', 'student-02', 'student-03', 'student-04', 'student-05')
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO professor_profiles (agent_id, academic_rank, specialty)
            SELECT id, '통합 교수', '통합마법학과 수업·시험·학생 지도'
            FROM agents
            WHERE fixture_key = 'professor-01'
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE agents
            SET openness = values.openness,
                conscientiousness = values.conscientiousness,
                extraversion = values.extraversion,
                agreeableness = values.agreeableness,
                emotional_stability = values.emotional_stability
            FROM (VALUES
              ('student-01', -25,  25, -25, -20,  0),
              ('student-02', -25, -25,  25, -20,  0),
              ('student-03',  25, -25, -25,  20,  0),
              ('student-04',  25,  25,  25, -20,  0),
              ('student-05', -25,  25,  25,  20,  0),
              ('professor-01', -20, 40, -25, 10, 35)
            ) AS values(fixture_key, openness, conscientiousness, extraversion, agreeableness, emotional_stability)
            WHERE agents.fixture_key = values.fixture_key
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE agent_states
            SET hunger = values.hunger,
                fatigue = values.fatigue,
                stress = values.stress,
                satisfaction = values.satisfaction,
                mood = values.mood,
                current_action = NULL
            FROM agents,
                 (VALUES
                   ('student-01', 25, 15, 20, 60,  0),
                   ('student-02', 35, 20, 15, 65, 10),
                   ('student-03', 20, 15, 20, 55,  0),
                   ('student-04', 25, 10, 25, 60,  5),
                   ('student-05', 30, 20, 15, 65, 10),
                   ('professor-01', 20, 15, 20, 70, 20)
                 ) AS values(fixture_key, hunger, fatigue, stress, satisfaction, mood)
            WHERE agent_states.agent_id = agents.id
              AND agents.fixture_key = values.fixture_key
            """
        )
    )

    op.drop_constraint("ck_agents_grade", "agents", type_="check")
    op.drop_column("agents", "grade")


def downgrade() -> None:
    op.add_column("agents", sa.Column("grade", sa.SmallInteger(), nullable=True))
    op.create_check_constraint("ck_agents_grade", "agents", "grade IS NULL OR grade BETWEEN 1 AND 4")
    op.execute(
        "UPDATE agents SET grade = student_profiles.grade "
        "FROM student_profiles WHERE agents.id = student_profiles.agent_id"
    )
    op.drop_table("professor_profiles")
    op.drop_table("student_profiles")

    for column in BIG_FIVE_COLUMNS:
        op.drop_constraint(f"ck_agents_{column}", "agents", type_="check")
        op.execute(f"UPDATE agents SET {column} = GREATEST(0, {column})")
        op.create_check_constraint(
            f"ck_agents_{column}", "agents", f"{column} BETWEEN 0 AND 100"
        )
        op.alter_column(
            "agents",
            column,
            existing_type=sa.SmallInteger(),
            server_default=sa.text("50"),
        )

    op.alter_column("agents", "fixture_version", existing_type=sa.String(50), nullable=True)
    op.alter_column("agents", "fixture_key", existing_type=sa.String(50), nullable=True)
