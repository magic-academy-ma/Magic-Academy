---
title: FR-01 Agent 상태 Policy
status: draft
updated: 2026-08-25
---

# FR-01 Agent 상태 Policy

## 1. 목적

Runtime의 정성적 state signal을 결정론적 delta로 변환하고 Agent 상태를 Tick transaction 안에서 안전하게 갱신한다.

## 2. 범위

**포함**
- 5개 상태의 state signal·intensity 기반 delta
- Conflict Resolver 합산
- 범위 clamp와 stale 검사
- 관계·Runtime Result와 동일한 Tick transaction

**제외**
- LLM 숫자 delta
- 밤 스킵 회복 규칙
- Event·Magic 전용 상태 효과
- 상태 이력 및 Replay snapshot 구현
- UI 표시

## 3. 입력 / 출력

| 항목 | 설명 |
|---|---|
| 입력 | Agent 상태 snapshot, state signal, policy version |
| 출력 | Agent·metric별 effect candidate와 최종 상태 |
| 저장 | `agent_states`의 현재 상태 |
| 오류 | invalid Agent, unknown metric, stale before, transaction 실패 |

## 4. 핵심 동작

1. Runtime 결과의 schema와 Agent ID를 검증한다.
2. state signal과 intensity를 승인된 delta 규칙으로 변환한다.
3. 동일 원인의 중복 signal을 제거한다.
4. 같은 Agent·metric의 서로 다른 effect를 합산한다.
5. 현재 snapshot 기준으로 최종값을 clamp한다.
6. DB 현재값이 before와 일치하는지 확인한다.
7. 상태·관계·Runtime Result를 하나의 Tick transaction에서 반영한다.

## 5. 경계 조건

- Agent State는 Agent당 정확히 한 행이다.
- 상태는 같은 Simulation의 Agent와 Location만 참조한다.
- 동일 metric의 UP/DOWN signal이 함께 있으면 둘 다 거부한다.
- 유효 Agent의 State가 없으면 기본값으로 생성하지 않고 Tick을 실패시킨다.
- stale 상태 또는 일부 write 실패 시 전체 Tick을 rollback한다.
- Policy Engine은 DB를 직접 commit하지 않는다.

## 6. 데이터 구조

| 상태 | 범위 |
|---|---:|
| hunger | 0~100 |
| fatigue | 0~100 |
| stress | 0~100 |
| satisfaction | 0~100 |
| mood | -100~100 |

## 7. 완료 기준

- [ ] 모든 상태 signal과 intensity 변환을 테스트한다.
- [ ] 상태별 상한·하한 clamp를 테스트한다.
- [ ] 동일 signal 중복 제거를 테스트한다.
- [ ] 상충 signal이 모두 거부되는지 테스트한다.
- [ ] 존재하지 않는 Agent·State를 거부한다.
- [ ] stale 상태가 Tick 전체 rollback을 유발한다.
- [ ] 관계·Runtime Result·Tick 번호도 함께 rollback된다.
- [ ] API 응답의 적용 delta가 DB 최종값과 일치한다.
- [ ] 단위·DB 통합·Tick E2E·Ruff·Mypy 검사가 통과한다.

## 8. 미정 항목

- 없음

## 9. 관련 문서

- `docs/02-domain/agents.md`
- `docs/03-system-design/policy-engine.md`
- `docs/03-system-design/policy-signal-delta.md`
- Confluence ERD v1.8
- PRD FR-01
