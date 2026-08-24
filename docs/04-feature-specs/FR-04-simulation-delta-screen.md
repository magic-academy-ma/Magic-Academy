> **상태**: Draft / **작성자**: Codex / **작성일**: 2026-08-25

## 0. 개요 및 목적

S5 시뮬레이션 메인 화면에서 성공한 Tick의 상태·관계 변화를 사용자에게 표시한다. 화면은 실제 Commit 결과만 표시하며 적용 전 preview를 최종 결과처럼 표현하지 않는다.

## 1. 컴포넌트 트리

```text
SimulationMainScreen
└── TickResultPanel
    ├── AgentStateDeltaSection
    │   ├── EmptyState
    │   └── DeltaGroup
    └── RelationshipDeltaSection
        ├── EmptyState
        └── RelationshipFlow
```

## 2. State / Props

| 이름 | 타입 | 출처 | 설명 |
|---|---|---|---|
| tickResult | TickAdvanceResponse | Tick API | 완료된 Tick 결과 |
| stateDeltas | StateDelta[] | tickResult | Agent 상태 변화 |
| relationshipDeltas | RelationshipDelta[] | tickResult | 방향성 관계 변화 |
| agentNameById | Record<UUID, string> | Agent API | UUID 대신 이름 표시 |
| tickLoading | boolean | 화면 state | Tick 실행 중 |
| tickError | TickError | API | 실행 실패 |

## 3. API 연동

| Method | Endpoint | 호출 시점 | 응답 |
|---|---|---|---|
| POST | `/v1/simulations/{id}/ticks/advance` | Tick 실행 | 상태·관계의 실제 적용 delta |
| GET | `/v1/simulations/{id}/agents` | 화면 진입 | Agent ID·이름 |

delta는 `effect_id`, source/target Agent ID, target type, metric, delta, before, after, rule ID, reason을 포함한다.

## 4. 빈 상태 / 로딩 / 에러 처리

- 실행 중에는 버튼 비활성화와 진행 메시지를 표시한다.
- 상태·관계 변화가 없으면 각각 빈 상태 메시지를 표시한다.
- 실패한 Tick은 이전 성공 결과를 새 결과처럼 표시하지 않는다.
- 401·403·409·5xx를 구분하고 허용되는 경우에만 재시도를 제공한다.
- 부분 Commit 상태는 허용하지 않는다.

## 5. Mock Data Fixture

```json
{
  "status": "COMPLETED",
  "state_deltas": [{
    "effect_id": "tick-1:student-1:fatigue",
    "source_agent_id": "00000000-0000-7000-8000-000000000001",
    "target_agent_id": null,
    "target_type": "AGENT_STATE",
    "metric": "fatigue",
    "delta": 3,
    "before": 15,
    "after": 18,
    "rule_id": "STATE_FATIGUE_UP_MEDIUM",
    "reason": "수업 참여"
  }],
  "relationship_deltas": [{
    "effect_id": "tick-1:student-1:student-2:trust",
    "source_agent_id": "00000000-0000-7000-8000-000000000001",
    "target_agent_id": "00000000-0000-7000-8000-000000000002",
    "target_type": "RELATIONSHIP",
    "metric": "trust",
    "delta": 3,
    "before": 20,
    "after": 23,
    "rule_id": "REL_TRUST_UP_MEDIUM",
    "reason": "협력 행동"
  }]
}
```

## 6. 테스트 포인트

- 상태와 관계 delta를 각각 렌더링한다.
- 양수·음수·0과 clamp 결과를 표시한다.
- UUID 대신 Agent 이름을 표시한다.
- A→B와 B→A를 다른 방향으로 표시한다.
- 성공한 Tick의 실제 `after`를 표시한다.
- 로딩·빈 결과·401·403·409·5xx를 처리한다.
- 실패한 Tick의 delta를 표시하지 않는다.
- 키보드 조작과 스크린리더 설명을 지원한다.
- API mock·컴포넌트 테스트·S5 E2E를 통과한다.

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|---|---|---|---|
| 1.0.0 | 2026-08-25 | 최초 작성 | Codex |
