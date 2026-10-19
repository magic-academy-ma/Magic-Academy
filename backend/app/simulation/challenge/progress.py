"""도전과제 모드 — project_progress 계산.

docs/04-feature-specs/challenge-mode-team-revival.md §6/§8: project_progress는
별도 컬럼·테이블에 저장하지 않고, 평가 시점에 해당 run의 GROUP_PROJECT Event
참여자 reaction.valence를 집계해 계산한다. POSITIVE는 증가, NEGATIVE는 감소,
NEUTRAL·미참여는 변화 없음.

DEFAULT_PROGRESS_STEP은 플레이테스트 후 조정 대상인 임시값이다 — 매직 넘버로
흩어놓지 않고 이름 있는 상수로 분리해 이후 쉽게 바꿀 수 있게 한다.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.simulation.agent_runtime import ReactionValence

DEFAULT_PROGRESS_STEP = 25  # 임시값 — 플레이테스트 후 조정

_PROGRESS_MIN = 0
_PROGRESS_MAX = 100


def calculate_project_progress(
    group_project_valences: Sequence[ReactionValence],
    *,
    start: int = 0,
    step: int = DEFAULT_PROGRESS_STEP,
) -> int:
    progress = start
    for valence in group_project_valences:
        if valence == ReactionValence.POSITIVE:
            progress += step
        elif valence == ReactionValence.NEGATIVE:
            progress -= step
    return max(_PROGRESS_MIN, min(_PROGRESS_MAX, progress))
