"""Slice 5 Task 6 — Tick 10 대표 캠페인 E2E 및 PASS 판정.

canonical campaign fixture(tests/slice5_campaign.py, Task 5)를 그대로 재사용하며,
이 파일은 새 결과를 만들지 않는다. 실제 Tick -> Event Master -> Magic -> Policy ->
Resolver -> Commit 경로가 만들어낸 결과만 검증한다.
"""

import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.simulation.agent_context_assembler import AgentContextAssembler
from tests.slice5_campaign import prepare_canonical_campaign, run_canonical_campaign


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required",
)


def test_canonical_campaign_reaches_tick_ten_without_interruption() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            campaign = run_canonical_campaign(db)
        outer.rollback()
    engine.dispose()

    # 10회 Tick 진행이 중단 없이 이어진다 (사전 히스토리 위에 이어지는 대표 캠페인).
    assert [tick.tick_number for tick in campaign] == list(
        range(campaign[0].tick_number, campaign[0].tick_number + 10)
    )


def test_agent_context_leakage_is_zero_across_full_campaign() -> None:
    """캠페인 10 Tick 동안 조립된 모든 AgentRuntimeInput에 비관찰자 정보가 없다."""
    captured = []
    original_assemble = AgentContextAssembler.assemble

    def recording_assemble(self, **kwargs):
        runtime_input = original_assemble(self, **kwargs)
        captured.append(runtime_input)
        return runtime_input

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            simulation, agents = prepare_canonical_campaign(db)
            full_roster_ids = {str(agent.id) for agent in agents.values()}

            AgentContextAssembler.assemble = recording_assemble
            try:
                import asyncio

                from app.services.manual_tick import advance_manual_tick
                from app.simulation.agent_runtime import AgentRuntime
                from tests.slice5_campaign import CanonicalCampaignLLM

                runtime = AgentRuntime(CanonicalCampaignLLM(), model="slice5-campaign")
                for _ in range(10):
                    asyncio.run(advance_manual_tick(db, simulation, runtime=runtime))
                    db.commit()
            finally:
                AgentContextAssembler.assemble = original_assemble
        outer.rollback()
    engine.dispose()

    assert len(captured) > 0
    leaks = 0
    for runtime_input in captured:
        observer_id = str(runtime_input.agent.agent_id)
        allowed_ids = {observer_id} | {
            str(summary.agent_id) for summary in runtime_input.nearby_agents
        }
        disallowed_ids = full_roster_ids - allowed_ids
        payload = json.dumps(runtime_input.model_dump(mode="json"))
        for hidden_id in disallowed_ids:
            if hidden_id in payload:
                leaks += 1
    assert leaks == 0


def test_rest_and_publisher_payloads_match_field_by_field_across_full_campaign() -> None:
    """REST 재조회 결과와 post-commit publisher payload가 필드 단위로 일치한다."""
    import asyncio

    from app.services.manual_tick import advance_manual_tick
    from app.services.simulation_events import build_tick_result_messages
    from app.simulation.agent_runtime import AgentRuntime
    from tests.slice5_campaign import CanonicalCampaignLLM

    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            simulation, agents = prepare_canonical_campaign(db)
            runtime = AgentRuntime(CanonicalCampaignLLM(), model="slice5-campaign")

            for _ in range(10):
                result = asyncio.run(advance_manual_tick(db, simulation, runtime=runtime))
                db.commit()

                relationship_deltas = [
                    {
                        "effect_id": effect.effect_id,
                        "rule_id": effect.rule_id,
                        "source_agent_id": str(effect.source_agent_id),
                        "target_agent_id": str(effect.target_agent_id),
                        "metric": effect.metric,
                        "before": effect.before,
                        "applied_delta": effect.after_preview - effect.before,
                        "after": effect.after_preview,
                        "reason": effect.reason,
                    }
                    for effect in result.policy_result.relationship_effects
                    if effect.target_agent_id is not None
                ]
                messages = build_tick_result_messages(
                    simulation.id, result.event_batch_result, relationship_deltas
                )
                tick_message = next(m for m in messages if m["type"] == "TICK_UPDATED")
                event_messages = [m for m in messages if m["type"] == "EVENT_CREATED"]

                assert tick_message["data"]["tick_number"] == result.event_batch_result[
                    "tick_number"
                ]
                assert (
                    tick_message["data"]["resolved_effects"]
                    == result.event_batch_result["resolved_effects"]
                )
                assert [
                    {
                        key: value
                        for key, value in item["data"].items()
                        if key not in {"simulation_id", "tick_number", "event_id"}
                    }
                    for item in event_messages
                ] == result.event_batch_result["events"]
        outer.rollback()
    engine.dispose()


def test_slice_zero_to_four_regression_suite_passes(pytestconfig) -> None:
    """Slice 0~4 누적 회귀: 기존 Slice 테스트 스위트가 여전히 통과한다."""
    import subprocess
    import sys

    regression_files = [
        "tests/test_slice_zero_api.py",
        "tests/test_slice1_e2e.py",
        "tests/test_slice2_policy_engine.py",
        "tests/test_relationship_repository.py",
        "tests/test_slice3_acceptance.py",
        "tests/test_slice3_memory_ab.py",
        "tests/test_slice3_tick_memory.py",
        "tests/test_simulation_tick_runtime.py",
    ]
    existing = [f for f in regression_files if os.path.exists(f)]
    assert existing, "Slice 0~4 회귀 테스트 파일을 찾을 수 없다."

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *existing, "-q"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
