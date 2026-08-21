"""add vector embedding and cosine HNSW index to agent memories

Revision ID: 20260814_0005
Revises: 20260810_0004
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa

revision = "20260814_0005"
down_revision = "20260810_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "agent_memories",
        sa.Column("embedding", Vector(1536), nullable=True),
    )
    op.create_index(
        "idx_agent_memories_embedding_hnsw",
        "agent_memories",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )


def downgrade() -> None:
    op.drop_index("idx_agent_memories_embedding_hnsw", table_name="agent_memories")
    op.drop_column("agent_memories", "embedding")
