"""Dialogue persistence — group mutual TALK utterances into retrievable dialogues.

Revision ID: 20260828_0002
Revises: 20260828_0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260828_0002"
down_revision = "20260828_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dialogues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "simulation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(length=100), nullable=False),
        sa.Column("tick_number", sa.BigInteger(), nullable=False),
        sa.Column(
            "participant_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "participant_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("tick_number >= 0", name="ck_dialogues_tick_number"),
        sa.CheckConstraint(
            "participant_a_id <> participant_b_id",
            name="ck_dialogues_distinct_participants",
        ),
        sa.UniqueConstraint(
            "simulation_id",
            "run_id",
            "tick_number",
            "participant_a_id",
            "participant_b_id",
            name="uq_dialogues_pair_per_tick",
        ),
    )
    op.create_index(
        "idx_dialogues_simulation_tick",
        "dialogues",
        ["simulation_id", "tick_number"],
    )
    op.create_table(
        "dialogue_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dialogue_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dialogues.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("message_order", sa.Integer(), nullable=False),
        sa.Column(
            "speaker_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
            nullable=False,
        ),
        sa.Column("utterance", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("message_order >= 0", name="ck_dialogue_messages_order"),
        sa.UniqueConstraint("dialogue_id", "message_order", name="uq_dialogue_messages_order"),
    )
    op.create_index(
        "idx_dialogue_messages_dialogue",
        "dialogue_messages",
        ["dialogue_id", "message_order"],
    )


def downgrade():
    """Refuse to silently discard persisted dialogues."""
    connection = op.get_bind()
    if connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM dialogues)")):
        raise RuntimeError("dialogue rows require an approved backfill before downgrade")
    op.drop_index("idx_dialogue_messages_dialogue", table_name="dialogue_messages")
    op.drop_table("dialogue_messages")
    op.drop_index("idx_dialogues_simulation_tick", table_name="dialogues")
    op.drop_table("dialogues")
