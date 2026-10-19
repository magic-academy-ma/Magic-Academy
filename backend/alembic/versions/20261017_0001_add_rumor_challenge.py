"""CHAPTER 1 private run state and durable command reservation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = '20261017_0001'
down_revision = '20260828_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('rumor_challenge_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('simulation_id', UUID(as_uuid=True), sa.ForeignKey('simulations.id'), nullable=False),
        sa.Column('start_request_id', UUID(as_uuid=True), nullable=False),
        sa.Column('seed', sa.BigInteger(), nullable=False),
        sa.Column('revision', sa.Integer(), server_default='0', nullable=False),
        sa.Column('private_state', JSONB(), nullable=False),
        sa.Column('receipts', JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('pending', JSONB(), nullable=True),
        sa.Column('intervention_opened_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('owner_id', 'start_request_id', name='uq_rumor_start_request'),
        sa.UniqueConstraint('simulation_id', name='uq_rumor_simulation'),
        sa.CheckConstraint('revision >= 0', name='ck_rumor_revision'),
    )


def downgrade():
    op.drop_table('rumor_challenge_runs')
