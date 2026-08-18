from typing import Literal, TypeAlias


# TODO(issue-41-task5): PR #42 Policy Engine도 통합 시 이 공통 계약을 import한다.
RelationshipMetric: TypeAlias = Literal[
    "affection",
    "closeness",
    "trust",
    "tension",
    "rivalry",
    "dependency",
]

RELATIONSHIP_METRIC_RANGES: dict[RelationshipMetric, tuple[int, int]] = {
    "affection": (-100, 100),
    "closeness": (-100, 100),
    "trust": (-100, 100),
    "tension": (0, 100),
    "rivalry": (0, 100),
    "dependency": (0, 100),
}
