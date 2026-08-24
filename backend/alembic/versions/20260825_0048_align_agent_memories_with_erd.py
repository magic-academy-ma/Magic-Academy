"""align agent memories with ERD v1.8

Revision ID: 20260825_0048
Revises: 20260812_0047
"""

import sqlalchemy as sa

from alembic import op

revision = "20260825_0048"
down_revision = "20260812_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_memories", sa.Column("simulation_id", sa.UUID(), nullable=True))
    op.add_column("agent_memories", sa.Column("embedding_model", sa.String(100), nullable=True))
    op.add_column("agent_memories", sa.Column("embedding_version", sa.String(50), nullable=True))
    op.add_column("agent_memories", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        UPDATE agent_memories AS memory
        SET simulation_id = agent.simulation_id
        FROM agents AS agent
        WHERE memory.agent_id = agent.id
        """
    )
    op.execute(
        """
        UPDATE agent_memories
        SET embedding_model = 'legacy-unknown',
            embedding_version = 'pre-metadata',
            embedded_at = updated_at
        WHERE embedding IS NOT NULL
        """
    )
    op.alter_column("agent_memories", "simulation_id", nullable=False)

    op.drop_constraint("fk_agent_memories_agent", "agent_memories", type_="foreignkey")
    op.drop_constraint("fk_agent_memories_event", "agent_memories", type_="foreignkey")
    op.create_unique_constraint(
        "uq_events_simulation_id_id", "events", ["simulation_id", "id"]
    )
    op.create_foreign_key(
        "fk_agent_memories_simulation",
        "agent_memories",
        "simulations",
        ["simulation_id"],
        ["id"],
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    )
    op.create_foreign_key(
        "fk_agent_memories_agent",
        "agent_memories",
        "agents",
        ["simulation_id", "agent_id"],
        ["simulation_id", "id"],
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    )
    op.create_foreign_key(
        "fk_agent_memories_event",
        "agent_memories",
        "events",
        ["simulation_id", "event_id"],
        ["simulation_id", "id"],
        ondelete="SET NULL (event_id)",
        onupdate="RESTRICT",
    )
    op.create_check_constraint(
        "ck_agent_memories_embedding_metadata",
        "agent_memories",
        "(embedding IS NULL AND embedding_model IS NULL AND embedding_version IS NULL AND embedded_at IS NULL) OR "
        "(embedding IS NOT NULL AND embedding_model IS NOT NULL AND embedding_version IS NOT NULL AND embedded_at IS NOT NULL)",
    )
    op.drop_index("idx_agent_memories_cleanup", table_name="agent_memories")
    op.create_index(
        "idx_agent_memories_cleanup",
        "agent_memories",
        ["agent_id", "importance", "created_tick", "id"],
    )


def downgrade() -> None:
    op.drop_index("idx_agent_memories_cleanup", table_name="agent_memories")
    op.create_index(
        "idx_agent_memories_cleanup",
        "agent_memories",
        ["agent_id", "importance", "created_tick"],
    )
    op.drop_constraint(
        "ck_agent_memories_embedding_metadata", "agent_memories", type_="check"
    )
    op.drop_constraint("fk_agent_memories_event", "agent_memories", type_="foreignkey")
    op.drop_constraint("fk_agent_memories_agent", "agent_memories", type_="foreignkey")
    op.drop_constraint("fk_agent_memories_simulation", "agent_memories", type_="foreignkey")
    op.drop_constraint("uq_events_simulation_id_id", "events", type_="unique")
    op.create_foreign_key(
        "fk_agent_memories_agent",
        "agent_memories",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="RESTRICT",
        onupdate="RESTRICT",
    )
    op.create_foreign_key(
        "fk_agent_memories_event",
        "agent_memories",
        "events",
        ["event_id"],
        ["id"],
        ondelete="SET NULL",
        onupdate="RESTRICT",
    )
    op.drop_column("agent_memories", "embedded_at")
    op.drop_column("agent_memories", "embedding_version")
    op.drop_column("agent_memories", "embedding_model")
    op.drop_column("agent_memories", "simulation_id")
