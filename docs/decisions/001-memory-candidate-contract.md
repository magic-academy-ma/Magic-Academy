---
authored_with: Claude Code
features_used: []
date: 2026-08-21
status: accepted
---

# 001. Runtime Memory 후보 계약 — IntentCandidate.memory_candidates로 통합

## 배경

Slice 3 Task 0(계약 동결)에서 `AgentRuntimeResult.memory_candidate: MemoryCandidateItem | None`
(단수, 검증 없는 plain dataclass)을 새 계약으로 정의하고 Task 2(#71, PR #107)에서 구현했다.

그러나 `docs/03-system-design/agent-runtime.md`(3.2 출력 계약, 4.2 GenerateMemoryCandidateNode)에는
이미 `IntentCandidate.memory_candidates: list[MemoryCandidate]`가 Runtime의 정식 출력으로 문서화돼
있었고, Slice 1에서 pydantic 검증(`importance` 1~10, `related_agent_ids`/`related_event_id` 유효성)까지
구현·테스트된 상태였다. Task 3(Tick Engine 연결, 이미 develop에 머지)도 이 기존 필드를 소비하도록
구현됐다.

두 계약이 병존하면서 Task 2가 추가한 필드는 실제 Tick 흐름에 연결되지 않은 죽은 코드가 된다.

## 결정

Runtime Memory 후보의 정식 계약은 기존 `IntentCandidate.memory_candidates`(리스트, pydantic 검증)로
확정한다. `AgentRuntimeResult.memory_candidate`(단수, Task 0-C/Task 2가 추가한 필드)는 폐기한다.

## 이유

- `agent-runtime.md`에 이미 문서화된 스펙과 일치한다 (JSON 예시: `memory_candidates` 배열, importance 1~10).
- Slice 1부터 검증된 코드(`validate_intent_candidate`의 `related_agent_ids`/`related_event_id` 검사)를
  재사용해 데이터 무결성이 더 높다.
- tick당 여러 Memory 후보를 허용해 실제 LLM 산출물과 더 잘 맞는다.
- 이미 완성·머지된 Task 3의 tick_engine.py 로직을 그대로 유지할 수 있어 회귀 리스크가 가장 낮다.
- 반대로 단수 필드를 정식화하면 Slice 1부터 쌓인 Runtime 핵심 스키마(`IntentCandidate`)를 변경해야 해
  영향 범위가 훨씬 크다.

## 결과

- PR #107(Task 2, 가윤님)의 `AgentRuntimeResult.memory_candidate` 필드·관련 테스트는 폐기하고,
  머지하지 않는다.
- Issue #71은 재정의: `IntentCandidate.memory_candidates`가 이미 정식 계약임을 명시하는 문서화
  작업으로 축소하거나 close 처리한다.
- Task 5(#74)의 남은 작업(enforce_cap(10) 테스트)은 기존 `intent.memory_candidates` 경로 기준으로
  진행한다.
- `local/docs/PLAN/1step slice/2026-08-09-slice3-memory-inspector.md`의 Task 0-C·Task 2 절은
  이 ADR로 대체됨을 표시한다.
- Task 0(계약 동결) 단계에서 기존 Runtime 스펙(`docs/03-system-design/agent-runtime.md`)을 확인하지
  않은 점이 근본 원인이며, 이는 계약 동결 담당(은혜)의 확인 누락이다.
