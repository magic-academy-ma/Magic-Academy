"""MVP Tick 시간 및 Event 발생 정책 — 단위 테스트 (DB 불필요).

계약: docs/04-feature-specs/mvp-tick-event-policy.md
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.event_magic_phase import (
    IMPACT_MULTIPLIER_BY_NAME,
    EventParameters,
    run_event_and_magic_phase,
)
from app.services.manual_tick import tick_position
from app.services.night_transition import (
    NightSkipConflictError,
    NightSkipNotAllowedError,
    apply_night_transition,
    skip_night,
)
from app.simulation.agent_runtime import Block
from app.simulation.event_master import (
    DYNAMIC_DAILY_MAX,
    AgentSummary,
    EventMaster,
    ImpactLevel,
    RelationshipSummary,
    ScheduledEventInput,
    _dynamic_frequency_allows,
)
from app.simulation.magic_layer import AgentSnapshot as MagicAgentSnapshot
from app.simulation.policy.models import AgentSnapshot as PolicyAgentSnapshot
from app.simulation.policy.registries.event_policy import build_event_effect_candidates


# ---------------------------------------------------------------------------
# §4.1 Tick 시간 구조 계약
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("tick", "day", "block"),
    [
        (1, 1, "MORNING"),
        (3, 1, "EVENING"),
        (4, 2, "MORNING"),
        (6, 2, "EVENING"),
        (7, 3, "MORNING"),
        (9, 3, "EVENING"),
        (10, 4, "MORNING"),
    ],
)
def test_tick_position_boundaries(tick, day, block):
    assert tick_position(tick) == (day, Block(block))


@pytest.mark.parametrize("bad", [0, -1, -3])
def test_tick_position_rejects_non_positive(bad):
    with pytest.raises(ValueError, match="positive"):
        tick_position(bad)


# ---------------------------------------------------------------------------
# §4.3 Event 발생 빈도
# ---------------------------------------------------------------------------
def _passing_seed(event_frequency: str) -> str:
    for tick in range(1, 500):
        seed = f"sim:{tick}:1"
        if _dynamic_frequency_allows(
            scheduled_count=0,
            event_frequency=event_frequency,
            frequency_seed=seed,
            daily_dynamic_count=0,
        ):
            return seed
    raise AssertionError("no passing seed found")


def test_frequency_gate_is_deterministic_for_same_seed():
    kwargs = {
        "scheduled_count": 0,
        "event_frequency": "medium",
        "frequency_seed": "sim:42:7",
        "daily_dynamic_count": 0,
    }
    assert _dynamic_frequency_allows(**kwargs) == _dynamic_frequency_allows(**kwargs)


def test_frequency_gate_blocks_when_three_or_more_scheduled():
    assert not _dynamic_frequency_allows(
        scheduled_count=3,
        event_frequency="high",
        frequency_seed=_passing_seed("high"),
        daily_dynamic_count=0,
    )


@pytest.mark.parametrize("event_frequency", ["low", "medium", "high"])
def test_frequency_gate_blocks_when_daily_cap_reached(event_frequency):
    cap = DYNAMIC_DAILY_MAX[event_frequency]
    assert not _dynamic_frequency_allows(
        scheduled_count=0,
        event_frequency=event_frequency,
        frequency_seed=_passing_seed(event_frequency),
        daily_dynamic_count=cap,
    )


def test_high_daily_cap_is_two_not_three():
    assert DYNAMIC_DAILY_MAX["high"] == 2


def _colocated_students(major: str = "고대 마법", location: str = "library", count: int = 2):
    return [
        AgentSummary(
            agent_id=f"s{i}",
            name=f"학생-{i}",
            role="student",
            major_id=major,
            year=1,
            active_status=True,
            current_location_id=location,
            mood=0,
            stress=10,
            fatigue=10,
        )
        for i in range(1, count + 1)
    ]


def test_legacy_path_without_seed_is_unchanged():
    """frequency_seed 없이 호출하면 빈도 정책이 적용되지 않는다 (Slice 5 동작)."""
    events = EventMaster().generate(tick=3, agent_summaries=_colocated_students())
    assert [e.event_type for e in events] == ["GROUP_PROJECT"]


def test_seeded_path_emits_at_most_one_dynamic_event():
    summaries = _colocated_students(count=2)
    relationships = [RelationshipSummary("s1", "s2", affection=20, closeness=20)]
    events = EventMaster().generate(
        tick=3,
        agent_summaries=summaries,
        relationship_summaries=relationships,
        event_frequency="high",
        frequency_seed=_passing_seed("high"),
    )
    dynamic = [e for e in events if e.event_type in {"GROUP_PROJECT", "MEETING"}]
    assert len(dynamic) <= 1


def test_seeded_path_daily_cap_reached_emits_no_dynamic_event():
    events = EventMaster().generate(
        tick=5,
        agent_summaries=_colocated_students(),
        event_frequency="medium",
        frequency_seed=_passing_seed("medium"),
        daily_dynamic_count=2,
    )
    assert [e for e in events if e.event_type in {"GROUP_PROJECT", "MEETING"}] == []


def test_cooldown_excludes_only_named_agents_from_group_project():
    summaries = _colocated_students(count=3)
    events = EventMaster().generate(
        tick=5,
        agent_summaries=summaries,
        event_frequency="high",
        frequency_seed=_passing_seed("high"),
        cooldown_excluded_agent_ids={"GROUP_PROJECT": frozenset({"s1"})},
    )
    group = [e for e in events if e.event_type == "GROUP_PROJECT"]
    assert group and "s1" not in group[0].participant_agent_ids
    assert {"s2", "s3"} <= set(group[0].participant_agent_ids)


def test_high_impact_today_agent_excluded_only_for_high_events():
    summaries = _colocated_students(count=3)
    high = EventMaster().generate(
        tick=5,
        agent_summaries=summaries,
        event_frequency="high",
        event_impact="high",
        frequency_seed=_passing_seed("high"),
        high_impact_agent_ids_today=frozenset({"s1"}),
    )
    group = [e for e in high if e.event_type == "GROUP_PROJECT"]
    assert group and "s1" not in group[0].participant_agent_ids

    medium = EventMaster().generate(
        tick=5,
        agent_summaries=summaries,
        event_impact="medium",
        frequency_seed=_passing_seed("medium"),
        high_impact_agent_ids_today=frozenset({"s1"}),
    )
    group_medium = [e for e in medium if e.event_type == "GROUP_PROJECT"]
    assert group_medium and "s1" in group_medium[0].participant_agent_ids


@pytest.mark.parametrize(
    ("event_impact", "importance", "cap"),
    [("low", 30, 2), ("medium", 50, 4), ("high", 80, 5)],
)
def test_dynamic_event_importance_and_participant_cap_by_impact(event_impact, importance, cap):
    summaries = _colocated_students(count=6)
    events = EventMaster().generate(
        tick=5,
        agent_summaries=summaries,
        event_impact=event_impact,
        event_frequency="high",
        frequency_seed=_passing_seed("high"),
    )
    group = [e for e in events if e.event_type == "GROUP_PROJECT"]
    assert group
    assert group[0].importance == importance
    assert len(group[0].participant_agent_ids) == cap


# ---------------------------------------------------------------------------
# §4.4 Event 영향도 배율
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("multiplier", "expected"),
    [(0.5, 4), (1.0, 8), (1.5, 12)],  # EXAM stress 기본 delta 8
)
def test_impact_multiplier_scales_and_rounds_base_effect(multiplier, expected):
    event = EventMaster().generate(
        tick=1,
        agent_summaries=[
            AgentSummary(
                agent_id="s1", name="s1", role="student", major_id=None, year=1,
                active_status=True, current_location_id="c1", mood=0, stress=0, fatigue=0,
            )
        ],
        scheduled_events=[
            ScheduledEventInput(
                event_id="e1", event_type="EXAM", location_id="c1",
                participant_agent_ids=("s1",), impact_level=ImpactLevel.MEDIUM,
            )
        ],
    )[0]
    snapshot = {"s1": PolicyAgentSnapshot(agent_id="s1", hunger=0, fatigue=0, stress=0, satisfaction=0)}
    candidates = build_event_effect_candidates(
        event, run_id="r1", agent_snapshots=snapshot, impact_multiplier=multiplier
    )
    stress = next(c for c in candidates if c.metric == "stress")
    assert stress.delta == expected


def test_impact_multiplier_map_matches_spec():
    assert IMPACT_MULTIPLIER_BY_NAME == {"low": 0.5, "medium": 1.0, "high": 1.5}


def test_run_event_and_magic_phase_applies_low_impact_multiplier():
    result = run_event_and_magic_phase(
        run_id="r1",
        tick=1,
        agent_summaries=[
            AgentSummary(
                agent_id="s1", name="s1", role="student", major_id="방어 마법", year=1,
                active_status=True, current_location_id="classroom", mood=0, stress=10, fatigue=10,
            )
        ],
        agent_state_snapshots={
            "s1": PolicyAgentSnapshot(agent_id="s1", hunger=0, fatigue=10, stress=10, satisfaction=0)
        },
        magic_agent_snapshots=[
            MagicAgentSnapshot(
                agent_id="s1", agent_type="student", active_status=True,
                current_location_id="classroom", fatigue=10, is_cursed=False,
            )
        ],
        scheduled_events=[
            ScheduledEventInput(
                event_id="e1", event_type="CLASS", location_id="classroom",
                participant_agent_ids=("s1",),
            )
        ],
        event_parameters=EventParameters(event_impact="low"),
    )
    # CLASS stress 기본 delta 1 × 0.5 -> round(0.5) == 0
    stress = [e for e in result.resolved_effects if e.metric == "stress"]
    assert stress == [] or stress[0].delta == 0


# ---------------------------------------------------------------------------
# §4.2 야간 전환 / night skip
# ---------------------------------------------------------------------------
class _FakeSession:
    """skip_night용 최소 세션 — advisory lock은 항상 획득 성공."""

    def __init__(self, *, lock: bool = True) -> None:
        self._lock = lock
        self.flush_count = 0

    def scalar(self, *_args, **_kwargs) -> bool:
        return self._lock

    def refresh(self, _obj, *, with_for_update: bool = False) -> None:
        return None

    def flush(self) -> None:
        self.flush_count += 1


def _sim(**overrides):
    base = {
        "id": uuid4(),
        "status": "running",
        "night_waiting": False,
        "current_tick": 3,
        "current_day": 1,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_apply_night_transition_advances_day_and_clears_flag():
    sim = _sim(night_waiting=True, current_day=1, current_tick=3)
    apply_night_transition(_FakeSession(), sim)
    assert sim.current_day == 2
    assert sim.current_tick == 3
    assert sim.night_waiting is False


def test_skip_night_transitions_when_night_waiting():
    sim = _sim(night_waiting=True, current_day=1, current_tick=3)
    outcome = skip_night(_FakeSession(), sim)
    assert outcome.transitioned is True
    assert sim.current_day == 2
    assert sim.current_tick == 3
    assert sim.night_waiting is False


def test_skip_night_is_idempotent_after_completed_transition():
    # 정상 전환 완료 상태 B: current_day == derived_day + 1
    sim = _sim(night_waiting=False, current_tick=3, current_day=2)
    outcome = skip_night(_FakeSession(), sim)
    assert outcome.transitioned is False
    assert sim.current_day == 2


def test_skip_night_conflicts_on_inconsistent_evening_state():
    # 상태 C: EVENING인데 night_waiting=False 이고 전환 흔적 없음
    sim = _sim(night_waiting=False, current_tick=3, current_day=1)
    with pytest.raises(NightSkipConflictError):
        skip_night(_FakeSession(), sim)


@pytest.mark.parametrize("current_tick", [1, 2, 4, 5])
def test_skip_night_conflicts_mid_day(current_tick):
    sim = _sim(night_waiting=False, current_tick=current_tick, current_day=(current_tick - 1) // 3 + 1)
    with pytest.raises(NightSkipConflictError):
        skip_night(_FakeSession(), sim)


@pytest.mark.parametrize("status", ["ready", "completed", "failed"])
def test_skip_night_not_allowed_for_non_running_statuses(status):
    sim = _sim(status=status, night_waiting=True)
    with pytest.raises(NightSkipNotAllowedError):
        skip_night(_FakeSession(), sim)


def test_skip_night_conflicts_when_lock_unavailable():
    sim = _sim(night_waiting=True)
    with pytest.raises(NightSkipConflictError):
        skip_night(_FakeSession(lock=False), sim)
