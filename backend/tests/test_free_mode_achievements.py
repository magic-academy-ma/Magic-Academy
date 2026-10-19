"""자유 모드 업적 5종 판정 (achievements.md §5.1)."""

from app.domain.achievements import ACHIEVEMENTS, AchievementMode
from app.simulation.free_mode_achievements import (
    CURSE_LIFTED,
    CURSE_SPREAD,
    CURSE_TRIGGERED,
    MAGIC_DISCOVERY,
    MISSING_STUDENT_RETURN,
    AgentStatus,
    event_witness_achievements,
    inspector_achievements,
    tick_achievements,
)

ACTIVE = "active"
MISSING = "inactive_temporary"


def _status(active_status=ACTIVE, cursed=False):
    return AgentStatus(active_status=active_status, cursed=cursed)


# ─── 실종된 학생의 귀환 목격 ──────────────────────────────────────────────────


def test_inspecting_returned_student_grants_return_witness():
    assert inspector_achievements(was_missing=True, active_status=ACTIVE) == {MISSING_STUDENT_RETURN}


def test_inspecting_student_who_never_went_missing_grants_nothing():
    assert inspector_achievements(was_missing=False, active_status=ACTIVE) == set()


def test_inspecting_student_still_missing_grants_nothing():
    assert inspector_achievements(was_missing=True, active_status=MISSING) == set()


# ─── 마법 발견 목격 ───────────────────────────────────────────────────────────


def test_opening_magical_discovery_event_grants_discovery_witness():
    assert event_witness_achievements("magical_discovery") == {MAGIC_DISCOVERY}
    assert event_witness_achievements("MAGICAL_DISCOVERY") == {MAGIC_DISCOVERY}


def test_opening_other_event_grants_nothing():
    assert event_witness_achievements("curse_spread") == set()
    assert event_witness_achievements("class") == set()


# ─── 저주 이벤트 발생 ─────────────────────────────────────────────────────────


def test_returned_student_getting_cursed_triggers_curse():
    before = {"a": _status(MISSING), "b": _status()}
    after = {"a": _status(cursed=True), "b": _status()}
    assert CURSE_TRIGGERED in tick_achievements(before, after)


def test_spread_without_return_is_not_a_new_trigger():
    before = {"a": _status(cursed=True), "b": _status()}
    after = {"a": _status(cursed=True), "b": _status(cursed=True)}
    assert CURSE_TRIGGERED not in tick_achievements(before, after)


# ─── 저주 확산 (동시 감염 3명 이상) ───────────────────────────────────────────


def test_three_cursed_at_once_grants_spread():
    before = {"a": _status(cursed=True), "b": _status(), "c": _status()}
    after = {"a": _status(cursed=True), "b": _status(cursed=True), "c": _status(cursed=True)}
    assert CURSE_SPREAD in tick_achievements(before, after)


def test_cumulative_infections_without_three_at_once_do_not_grant_spread():
    # 누적으로는 3명이 저주에 걸렸지만 동시에는 2명뿐이다.
    before = {"a": _status(cursed=True), "b": _status(cursed=True), "c": _status()}
    after = {"a": _status(), "b": _status(), "c": _status(cursed=True)}
    assert CURSE_SPREAD not in tick_achievements(before, after)


# ─── 저주 해결 ────────────────────────────────────────────────────────────────


def test_curses_ending_together_grants_lifted():
    before = {"a": _status(cursed=True), "b": _status(cursed=True)}
    after = {"a": _status(), "b": _status()}
    assert tick_achievements(before, after) == {CURSE_LIFTED}


def test_no_curse_change_grants_nothing():
    before = {"a": _status(), "b": _status(cursed=True)}
    assert tick_achievements(before, before) == set()


# ─── 카탈로그 ─────────────────────────────────────────────────────────────────


def test_every_free_mode_achievement_has_a_judgement():
    judged = {
        *inspector_achievements(was_missing=True, active_status=ACTIVE),
        *event_witness_achievements("MAGICAL_DISCOVERY"),
        *tick_achievements(
            {"a": _status(MISSING), "b": _status(), "c": _status()},
            {"a": _status(cursed=True), "b": _status(cursed=True), "c": _status(cursed=True)},
        ),
        *tick_achievements({"a": _status(cursed=True)}, {"a": _status()}),
    }
    free = {a.id for a in ACHIEVEMENTS if a.mode == AchievementMode.FREE}
    assert judged == free
