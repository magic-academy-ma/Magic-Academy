"""add simulation_configs.magic_layer_frequency / magic_layer_impact

Revision ID: 20260828_0001
Revises: 20260827_0013

Magic Layer 초기 파라미터(빈도·영향도)를 기존 버전형 ``simulation_configs`` 테이블에
컬럼으로 추가한다. 별도 테이블/스냅샷을 만들지 않고 ``event_frequency`` /
``event_impact`` 와 동일한 저장·버전·스냅샷 경로를 그대로 재사용한다
(docs/01-product/simulation-parameters.md §2).
"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_0001"
down_revision = "20260827_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_configs",
        sa.Column(
            "magic_layer_frequency",
            sa.String(length=10),
            nullable=False,
            server_default="medium",
        ),
    )
    op.add_column(
        "simulation_configs",
        sa.Column(
            "magic_layer_impact",
            sa.String(length=10),
            nullable=False,
            server_default="medium",
        ),
    )
    op.create_check_constraint(
        "ck_simulation_configs_magic_layer_frequency",
        "simulation_configs",
        "magic_layer_frequency IN ('low', 'medium', 'high')",
    )
    op.create_check_constraint(
        "ck_simulation_configs_magic_layer_impact",
        "simulation_configs",
        "magic_layer_impact IN ('low', 'medium', 'high')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_simulation_configs_magic_layer_impact", "simulation_configs", type_="check"
    )
    op.drop_constraint(
        "ck_simulation_configs_magic_layer_frequency", "simulation_configs", type_="check"
    )
    op.drop_column("simulation_configs", "magic_layer_impact")
    op.drop_column("simulation_configs", "magic_layer_frequency")
