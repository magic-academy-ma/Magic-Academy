"""PR2 — Magic 파라미터 연결 단위 테스트 (DB 불필요).

계약: docs/01-product/simulation-parameters.md §4–§6, PR2 스펙.
- Magic frequency 확률 게이트 (조건 충족 후보에만, seed 재현)
- Magic impact 효과 강도 배율
- magic_enabled=false OFF 조건 (threshold 0.7)
"""

import pytest

from app.services.event_magic_phase import (
    EventParameters,
    run_event_and_magic_phase,
)
from app.services.simulation_snapshots import (
    MAGIC_OFF_IMPACT_THRESHOLD,
    NORMALIZED_MAGIC_IMPACT,
    magic_off_eligible,
)
from app.simulation.magic_layer import (
    MAGIC_DAILY_MAX,
    MAGIC_FREQUENCY_PROBABILITY,
    STUDENT_MISSING,
    AgentSnapshot,
    MagicLayer,
)
from app.simulation.policy.models import AgentSnapshot as PolicyAgentSnapshot
from app.simulation.policy.registries.event_policy import build_magic_effect_candidates


# ---------------------------------------------------------------------------
# magic_off_eligible — OFF 조건 (simulation-parameters.md §6)
# ---------------------------------------------------------------------------
def test_magic_off_threshold_and_normalized_values_are_fixed():
    assert MAGIC_OFF_IMPACT_THRESHOLD == 0.7
    assert NORMALIZED_MAGIC_IMPACT == {"low": 0.3, "medium": 0.5, "high": 0.8}


@pytest.mark.parametrize(
    ("impact", "eligible"),
    [("low", False), ("medium", False), ("high", True)],
)
def test_magic_off_eligible_only_for_high(impact, eligible):
    assert magic_off_eligible(impact) is eligible


# ---------------------------------------------------------------------------
# Magic frequency 게이트 (PR2 스펙 §2)
# ---------------------------------------------------------------------------
def _missing_candidate(agent_id: str = "s1") -> AgentSnapshot:
    return AgentSnapshot(
        agent_id=agent_id,
        agent_type="student",
        active_status=True,
        current_location_id="dormitory",
        fatigue=10,
        is_cursed=False,
        recent_stress=tuple([95] * 10),
    )


def test_frequency_map_matches_spec():
    assert MAGIC_FREQUENCY_PROBABILITY == {"low": 0.25, "medium": 0.50, "high": 0.75}
    assert MAGIC_DAILY_MAX == {"low": 1, "medium": 2, "high": 3}


def test_no_seed_keeps_legacy_behavior_all_condition_candidates_pass():
    result = MagicLayer().evaluate(
        tick=11, regular_events=[], agent_snapshots=[_missing_candidate()]
    )
    assert [e.event_subtype for e in result.special_events] == [STUDENT_MISSING]


def test_frequency_gate_is_deterministic_for_same_seed():
    kwargs = {
        "tick": 11,
        "regular_events": [],
        "agent_snapshots": [_missing_candidate()],
        "magic_frequency": "medium",
        "magic_frequency_seed": "sim-1:11:1",
    }
    first = MagicLayer().evaluate(**kwargs)
    second = MagicLayer().evaluate(**kwargs)
    assert [e.event_subtype for e in first.special_events] == [
        e.event_subtype for e in second.special_events
    ]


def test_frequency_gate_suppresses_more_at_low_than_at_high():
    passed_low = 0
    passed_high = 0
    for i in range(200):
        seed = f"sim:{i}:1"
        if MagicLayer().evaluate(
            tick=11,
            regular_events=[],
            agent_snapshots=[_missing_candidate()],
            magic_frequency="low",
            magic_frequency_seed=seed,
        ).special_events:
            passed_low += 1
        if MagicLayer().evaluate(
            tick=11,
            regular_events=[],
            agent_snapshots=[_missing_candidate()],
            magic_frequency="high",
            magic_frequency_seed=seed,
        ).special_events:
            passed_high += 1
    # low(25%) 는 일부를 차단하고, high(75%) 는 low 보다 더 많이 통과시킨다.
    assert 0 < passed_low < 200
    assert passed_high > passed_low


def test_daily_cap_blocks_when_reached():
    result = MagicLayer().evaluate(
        tick=11,
        regular_events=[],
        agent_snapshots=[_missing_candidate()],
        magic_frequency="low",
        magic_frequency_seed="sim:seed-pass:1",
        magic_daily_count=1,  # low 하루 최대 1 -> 이미 도달
    )
    assert result.special_events == ()


def test_tick_cap_limits_to_one_special_event():
    snaps = [_missing_candidate("s1"), _missing_candidate("s2")]
    result = MagicLayer().evaluate(tick=11, regular_events=[], agent_snapshots=snaps)
    # 후보가 2명이어도 Tick 당 최대 1개.
    assert len(result.special_events) == 1


# ---------------------------------------------------------------------------
# Magic impact 배율 (PR2 스펙 §3)
# ---------------------------------------------------------------------------
def test_magic_impact_multiplier_scales_effect_delta():
    from app.simulation.magic_layer import SpecialEvent

    special = SpecialEvent(
        event_subtype="MAGIC_EXPLOSION",
        participant_agent_ids=("s1",),
        location_id="lab",
        tick=1,
        title="마법 폭발",
        affected_agent_ids=("s1",),
    )
    snapshot = {
        "s1": PolicyAgentSnapshot(
            agent_id="s1", hunger=0, fatigue=0, stress=0, satisfaction=0
        )
    }
    base = build_magic_effect_candidates(
        [special], run_id="r1", agent_snapshots=snapshot, impact_multiplier=1.0
    )
    high = build_magic_effect_candidates(
        [special], run_id="r1", agent_snapshots=snapshot, impact_multiplier=1.5
    )
    base_stress = next(c for c in base if c.metric == "stress").delta
    high_stress = next(c for c in high if c.metric == "stress").delta
    assert high_stress == round(base_stress * 1.5)


def test_magic_enabled_false_skips_special_events():
    result = run_event_and_magic_phase(
        run_id="r1",
        tick=11,
        agent_summaries=[],
        agent_state_snapshots={},
        magic_agent_snapshots=[
            AgentSnapshot(
                agent_id="s1",
                agent_type="student",
                active_status=True,
                current_location_id="dormitory",
                fatigue=10,
                is_cursed=False,
                recent_stress=tuple([95] * 10),
            )
        ],
        event_parameters=EventParameters(magic_enabled=False),
    )
    assert result.special_events == ()


def test_magic_enabled_true_still_emits_special_events_without_seed():
    result = run_event_and_magic_phase(
        run_id="r1",
        tick=11,
        agent_summaries=[],
        agent_state_snapshots={
            "s1": PolicyAgentSnapshot(
                agent_id="s1", hunger=0, fatigue=10, stress=95, satisfaction=0
            )
        },
        magic_agent_snapshots=[
            AgentSnapshot(
                agent_id="s1",
                agent_type="student",
                active_status=True,
                current_location_id="dormitory",
                fatigue=10,
                is_cursed=False,
                recent_stress=tuple([95] * 10),
            )
        ],
        event_parameters=EventParameters(magic_enabled=True, magic_impact="low"),
    )
    assert [e.event_subtype for e in result.special_events] == [STUDENT_MISSING]
    assert result.magic_impact == "low"
