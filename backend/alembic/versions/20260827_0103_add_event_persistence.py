"""Task 3 Event results and persistent curse expiration.

Revision ID: 20260827_0103
Revises: 20260812_0047
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260827_0103"
down_revision = "20260812_0047"
branch_labels = None
depends_on = None

REGULAR = "'class', 'group_project', 'exam', 'meeting', 'mt', 'festival', 'student_council', 'random_incident'"
MAGIC = "'student_missing', 'curse_spread', 'magic_explosion', 'ritual_failure', 'magical_discovery'"


def upgrade():
    """Extend the existing schema without rewriting previously applied revisions."""
    op.add_column("agents", sa.Column("cursed_until_tick", sa.BigInteger(), nullable=True))
    op.create_check_constraint("ck_agents_cursed_until_tick", "agents", "cursed_until_tick IS NULL OR cursed_until_tick >= 0")
    op.drop_constraint("ck_events_type", "events", type_="check")
    op.create_check_constraint("ck_events_type", "events", f"event_type IN ({REGULAR}, {MAGIC})")
    op.create_table(
        "event_batch_results",
        sa.Column("simulation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("simulations.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("tick_number", sa.BigInteger(), primary_key=True),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tick_number >= 1", name="ck_event_batch_results_tick"),
    )


def downgrade():
    """Refuse to discard persisted results or live curse state silently."""
    connection = op.get_bind()
    if connection.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM events WHERE event_type IN ({MAGIC})) OR EXISTS(SELECT 1 FROM event_batch_results) OR EXISTS(SELECT 1 FROM agents WHERE cursed_until_tick IS NOT NULL)")):
        raise RuntimeError("Task 3 data requires an approved backfill before downgrade")
    op.drop_table("event_batch_results")
    op.drop_constraint("ck_events_type", "events", type_="check")
    op.create_check_constraint("ck_events_type", "events", f"event_type IN ({REGULAR})")
    op.drop_constraint("ck_agents_cursed_until_tick", "agents", type_="check")
    op.drop_column("agents", "cursed_until_tick")
