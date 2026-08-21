---
title: Slice 6 — 설정 저장·Replay·시점 복원 계약
status: approved
updated: 2026-08-21
visibility: public
source:
  - "GitHub Issue #116"
  - "GitHub Issue #117"
  - "docs/03-system-design/event-master.md"
  - "docs/03-system-design/tick-engine.md"
---

# Slice 6 — 설정 저장·Replay·시점 복원 계약

> 이 문서는 Slice 6 Task 0에서 동결한 설정 저장·Replay·시점 복원 구현 계약이다.

## 1. 목적

Simulation 설정과 실행 시점의 상태를 보존하고, 저장된 기록만으로 Replay하거나 지정 시점의 상태를 복원한다.

Slice 6의 핵심 불변 조건은 다음과 같다.

- Replay는 Runtime, LLM, Tick Engine을 호출하지 않는다.
- Replay는 새 Tick, Intent, Event, Memory 또는 관계 변화를 생성하지 않는다.
- Replay 결과의 순서와 식별자는 원본 실행 기록과 같아야 한다.
- 복원과 설정 변경은 인증된 Simulation 소유자만 수행한다.
- Snapshot 저장 또는 복원 중 하나라도 실패하면 전체 transaction을 rollback한다.

## 2. 용어와 책임 경계

| 용어 | 정의 |
| --- | --- |
| Simulation 설정 | Tick 실행 조건에 영향을 주는 버전 관리 대상 값 |
| Snapshot | 특정 Simulation 시점의 복원 가능한 상태 묶음 |
| Replay | Snapshot과 실행 기록을 읽어 과거 결과를 순서대로 조회하는 read-only 동작 |
| 복원 | 선택한 Snapshot의 상태를 다시 현재 상태로 적용하는 write 동작 |
| 원본 실행 | Runtime·Policy·Resolver·Commit을 거쳐 실제 상태를 만든 Tick 실행 |

### 범위에 포함

- 설정 저장 및 버전 기록
- 성공한 실행 시점 Snapshot 저장
- Snapshot과 실행 기록 조회
- 지정 시점 상태 복원
- Replay 무재실행 보장
- 소유권 및 오류 응답

### 범위에서 제외

- 과거 입력으로 Runtime·LLM·Tick을 다시 실행하는 재시뮬레이션
- 원본 실행 기록 수정
- 여러 Simulation 사이의 Snapshot 공유
- 사용자 임의 Snapshot 편집

## 3. 기존 문서에서 확정된 계약

### 3.1 설정

일반 Event 설정은 다음 두 값을 사용한다.

| 필드 | 허용값 | 기본값 |
| --- | --- | --- |
| `event_frequency` | `low`, `medium`, `high` | `medium` |
| `event_impact` | `low`, `medium`, `high` | `medium` |

- 실행 중 변경한 설정은 현재 Tick에 영향을 주지 않고 다음 Tick Snapshot부터 적용한다.
- Tick 실행과 설정 변경이 경합하면 현재 Tick은 기존 설정으로 완료한다.
- Replay와 복원은 각 Tick에 저장된 설정 Snapshot을 사용한다.
- 동적 Event 확률 판정은 `simulation_id`, `tick_number`, 해당 Tick 설정 Snapshot을 입력으로 사용한다.

### 3.2 Tick 실행 기록

- Tick 시작 world state는 `REPEATABLE READ`로 조회한다.
- 상태 변화는 Tick 단위 batch commit으로 저장한다.
- commit에 실패한 Tick은 완료 Snapshot 및 Replay 대상이 될 수 없다.
- Runtime 결과에는 `run_id`, `tick_number`, `agent_id`, `idempotency_key`, `result_fingerprint`가 존재한다.

## 4. 확정 계약

### 4.1 Snapshot 경계

- Snapshot은 성공한 Tick batch commit 직후 상태를 나타낸다.
- Tick 0 초기 상태도 하나의 Snapshot으로 저장한다.
- 식별자는 UUIDv7 `snapshot_id`를 사용한다.
- `(simulation_id, tick_number)`는 유일해야 한다.
- 저장 중 실패하면 Tick의 다른 변경과 함께 rollback한다.

### 4.2 Snapshot 최소 범위

- Simulation: 상태, 현재 day/tick, 적용 설정 버전
- Agent: 활성 상태, 비활성 종료 Tick, Persona 잠금 상태
- Agent State: 위치, 내부 상태, 현재 행동
- 방향성 Relationship 전체
- Organization membership 상태
- Event와 Event participant 결과
- Agent Memory
- Runtime 결과와 실행 식별자
- 해당 Tick에 적용된 설정값과 정책·Resolver 버전

Snapshot은 원본 행을 참조하는 링크만 저장하지 않고, 복원에 필요한 값을 불변 payload로 보존한다.

### 4.3 Replay

- Replay API는 Snapshot과 저장된 실행 기록만 조회한다.
- 기본 순서는 `tick_number ASC`이며 같은 Tick에서는 원본 저장 순서를 보존한다.
- Replay 요청은 Simulation의 현재 상태를 변경하지 않는다.
- 원본 기록이나 Snapshot이 누락되거나 서로 일치하지 않으면 새 실행으로 보완하지 않고 오류를 반환한다.

### 4.4 복원

- 소유권 확인 후 한 transaction에서 복원한다.
- 선택 Snapshot 이후의 원본 기록은 삭제하거나 덮어쓰지 않는다.
- 복원 결과는 기존 Simulation을 과거 시점으로 되감지 않고 새 Simulation 분기로 생성한다.
- 복원된 Simulation은 새 ID를 가지며 원본 Simulation과 Snapshot 출처를 기록한다.

### 4.5 오류 계약

| 상황 | HTTP | 오류 코드 |
| --- | ---: | --- |
| 인증 정보 없음·유효하지 않음 | 401 | `AUTHENTICATION_REQUIRED` |
| 다른 사용자의 Simulation·Snapshot 접근 | 403 | `SIMULATION_ACCESS_DENIED` |
| Simulation·Snapshot·실행 기록 없음 | 404 | `REPLAY_RESOURCE_NOT_FOUND` |
| 잘못된 tick·설정값·요청 조합 | 400 | `INVALID_REPLAY_REQUEST` |
| 실행 중 설정 잠김·복원 불가 상태 | 409 | `RESTORE_CONFLICT` |
| Snapshot과 실행 기록 불일치 | 409 | `SNAPSHOT_MISMATCH` |

## 5. Task 경계와 통합 순서

| Task | 책임 | 선행 조건 |
| --- | --- | --- |
| Task 0 (#117) | 본 계약 확정 및 증빙 기준 동결 | 없음 |
| Task 1 (#118) | 설정·Snapshot 저장, 조회·복원 transaction | Task 0 |
| Task 3 (#120) | 설정·Replay·복원 UI와 오류 표시 | Task 0, API 연동은 Task 1 |
| Task 4 (#121) | Runtime·LLM·Tick 호출 0회 검증과 guard | Task 0, 통합 검증은 Task 1 |
| Task 2 (#119) | 인수·누적 회귀 및 최종 증빙 | Task 1·3·4 |

모든 Task 브랜치는 `feature/issue-116-slice6-base`에서 분기하고 Task PR의 base도 같은 브랜치로 지정한다.

각 Task의 실행 명령과 PASS 결과는 해당 Task PR의 `테스트 / 확인 내용`에 기록하고 Parent #116에 링크를 남긴다. Task 2는 Task 1·3·4의 증빙을 취합해 최종 인수·누적 회귀 결과를 같은 위치에 기록한다.

## 6. Task 0 결정 사항

1. **복원 방식**: 기존 Simulation을 되감지 않고 새 Simulation 분기로 복원한다.
2. **Snapshot 생성 단위**: Tick 0과 성공한 모든 Tick의 batch commit 직후 Snapshot을 저장한다.
3. **Snapshot 상태 범위**: 4.2의 전체 범위를 불변 payload로 저장한다.
4. **설정 범위**: `event_frequency`, `event_impact`, `magic_enabled`, User Persona 설정을 버전 관리한다.
5. **보존 정책**: MVP에서는 Snapshot을 기간·개수 제한 없이 보존한다.
6. **동일 Tick 정렬 기준**: Tick 안의 원본 출력 순서를 보존하는 별도 sequence를 저장한다.

## 7. Task 0 완료 기준

- [x] 6장의 모든 항목이 확정되어 있다.
- [x] Task 1·3·4가 동일한 설정·Snapshot·Replay 계약을 참조한다.
- [x] Replay 무재실행 규칙과 실패 방식이 명확하다.
- [x] Snapshot 저장 및 복원 transaction 경계가 명확하다.
- [x] API 오류 상태가 확정되어 있다.
- [x] Task별 테스트 증빙 위치와 최종 통합 순서가 합의되어 있다.
