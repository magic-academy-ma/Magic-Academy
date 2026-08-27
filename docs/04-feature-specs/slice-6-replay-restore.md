---
title: Slice 6 — 설정 저장·Replay·시점 복원 계약
status: approved
updated: 2026-08-26
visibility: public
source:
  - "GitHub Issue #116"
  - "GitHub Issue #117"
  - "docs/01-product/functional-requirements.md"
  - "docs/01-product/simulation-parameters.md"
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
- 설정 조회·변경, Snapshot 조회, Replay 및 복원은 인증된 Simulation 소유자만 수행한다.
- Snapshot 저장에 실패하면 같은 Tick transaction 전체를 rollback한다.
- 조회·복원은 읽기 전용이며 성공·실패와 관계없이 DB 상태를 변경하지 않는다.

## 2. 용어와 책임 경계

| 용어 | 정의 |
| --- | --- |
| Simulation 설정 | Tick 실행 조건에 영향을 주는 버전 관리 대상 값 |
| Snapshot | 특정 Simulation 시점의 복원 가능한 상태 묶음 |
| Replay | Snapshot과 실행 기록을 읽어 과거 결과를 순서대로 조회하는 read-only 동작 |
| 복원 | 선택한 Snapshot의 상태·관계·Memory를 읽기 전용으로 재구성하는 동작 |
| 원본 실행 | Runtime·Policy·Resolver·Commit을 거쳐 실제 상태를 만든 Tick 실행 |

### 범위에 포함

- 설정 저장 및 버전 기록
- 성공한 실행 시점 Snapshot 저장
- Snapshot과 실행 기록 조회
- 지정 시점 Snapshot 조회 및 상태 재구성
- Replay 무재실행 보장
- 소유권 및 오류 응답

### 범위에서 제외

- 과거 입력으로 Runtime·LLM·Tick을 다시 실행하는 재시뮬레이션
- 원본 실행 기록 수정
- Snapshot을 적용한 새 Simulation 분기 생성과 계보 관리
- 여러 Simulation 사이의 Snapshot 공유
- 사용자 임의 Snapshot 편집

## 3. 기존 문서에서 확정된 계약

### 3.1 설정

일반 Event 및 Magic Layer의 빈도·영향도 설정은 다음 값을 사용한다.

| 필드 | 허용값 | 기본값 |
| --- | --- | --- |
| `event_frequency` | `low`, `medium`, `high` | `medium` |
| `event_impact` | `low`, `medium`, `high` | `medium` |
| `magic_frequency` | `low`, `medium`, `high` | `medium` |
| `magic_impact` | `low`, `medium`, `high` | `medium` |

- 일반 Event의 `event_frequency`, `event_impact`는 `ready`, `running`, `paused`
  상태에서 변경할 수 있다. 실행 중 변경은 현재 Tick에 영향을 주지 않고 다음 Tick
  Snapshot부터 적용한다.
- Tick 실행과 일반 Event 설정 변경이 경합하면 현재 Tick은 시작 시 고정한 기존 설정
  버전으로 완료하고 변경값은 다음 Tick부터 적용한다.
- `magic_enabled`, `magic_frequency`, `magic_impact`와 User Persona 설정은 `ready`에서만 변경할 수 있으며 Simulation
  시작 후에는 고정한다.
- 초기 seed는 Simulation 생성 시 사용한 실제 값을 초기 설정 버전에 저장하고 이후
  설정 버전에도 보존한다. Tick별 실행 seed와 구분하며 Replay·복원 시 재생성하지 않는다.
- 일반 Event 설정, Magic 설정, User Persona 설정 및 초기 seed를 설정 버전의 저장
  범위에 포함한다. Tick 0과 이후 모든 Snapshot은 해당 시점의 설정 버전과 실제 값을
  불변 payload로 보존하며 현재 설정을 다시 조회해 과거 값을 대체하지 않는다.
- Replay와 복원은 각 Tick에 저장된 설정 Snapshot을 사용한다.
- 동적 Event 확률 판정은 `simulation_id`, `tick_number`, 해당 Tick 설정 Snapshot을 입력으로 사용한다.

### 3.2 Tick 실행 기록

- Tick 시작 world state는 `REPEATABLE READ`로 조회한다.
- 상태 변화는 Tick 단위 batch commit으로 저장한다.
- commit에 실패한 Tick은 완료 Snapshot 및 Replay 대상이 될 수 없다.
- Runtime 결과에는 `run_id`, `tick_number`, `agent_id`, `idempotency_key`, `result_fingerprint`가 존재한다.

## 4. 확정 계약

### 4.1 Snapshot 경계

- Snapshot은 Tick의 다른 상태 변화와 같은 transaction에서 commit 직전에 저장한다.
- Tick 결과와 Snapshot 저장이 모두 성공한 경우에만 한 번에 commit하며, 저장된
  Snapshot은 해당 batch commit 직후 상태를 나타낸다.
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
- Runtime 결과와 실행 식별자(원본 Replay·감사용)
- 해당 Tick에 적용된 설정 버전·설정값(일반 Event·Magic 빈도/영향도,
  `magic_enabled`, User Persona, 초기 seed)과 정책·Resolver 버전

Snapshot은 원본 행을 참조하는 링크만 저장하지 않고, 복원과 Replay에 필요한 값을
불변 payload로 보존한다. Runtime 결과는 원본 Replay·감사용 실행 이력으로 payload에
보존한다. 조회·복원은 payload를 읽어 응답을 재구성할 뿐 DB 행을 생성·수정·삭제하지
않는다.

### 4.3 Replay

- Replay API는 Snapshot과 저장된 실행 기록만 조회한다.
- Replay 목록·상세 조회 모두 인증 및 Simulation 소유권을 검사한다.
- 기본 순서는 `tick_number ASC`이며 같은 Tick에서는 원본 저장 순서를 보존한다.
- Replay 요청은 Simulation의 현재 상태를 변경하지 않는다.
- 원본 기록이나 Snapshot이 누락되거나 서로 일치하지 않으면 새 실행으로 보완하지 않고 오류를 반환한다.

### 4.4 시점 복원

- 인증된 Simulation 소유자만 Snapshot을 조회·복원할 수 있다.
- 복원 응답은 선택한 Tick의 상태·관계·Memory를 Snapshot payload에서 재구성한다.
- 복원은 원본 Simulation의 현재 상태, 실행 기록, Snapshot을 변경하지 않는다.
- 복원은 새 Simulation, Tick, Runtime 결과 또는 실행 계보를 생성하지 않는다.
- Runtime, LLM, Tick Engine, Event Master와 Magic Layer를 호출하지 않는다.
- Snapshot payload와 저장된 실행 기록이 일치하지 않으면 새 실행으로 보완하지 않고
  오류를 반환한다.

### 4.5 오류 계약

| 상황 | HTTP | 오류 코드 |
| --- | ---: | --- |
| 인증 정보 없음·유효하지 않음 | 401 | `AUTHENTICATION_REQUIRED` |
| 다른 사용자의 Simulation·Snapshot 접근 | 403 | `SIMULATION_ACCESS_DENIED` |
| Simulation·Snapshot·실행 기록 없음 | 404 | `REPLAY_RESOURCE_NOT_FOUND` |
| 잘못된 tick·설정값·요청 조합 | 400 | `INVALID_REPLAY_REQUEST` |
| 변경할 수 없는 상태에서 일반 Event 설정 변경 | 409 | `SIMULATION_SETTINGS_LOCKED` |
| 시작 후 Magic·Persona 설정 변경 | 409 | `INITIAL_SETTINGS_LOCKED` |
| Snapshot과 실행 기록 불일치 | 409 | `SNAPSHOT_MISMATCH` |
| 지원하지 않는 Snapshot schema version | 409 | `UNSUPPORTED_SNAPSHOT_SCHEMA` |

Replay 목록·상세, Snapshot 조회·복원, 설정 조회·변경 각각에 대해 인증 정보 없음·
유효하지 않음은 401, 다른 사용자 소유 리소스 접근은 403임을 검증한다.

## 5. Task 경계와 통합 순서

| Task | 책임 | 선행 조건 |
| --- | --- | --- |
| Task 0 (#117) | 본 계약 확정 및 증빙 기준 동결 | 없음 |
| Task 1 (#118) | 설정·Snapshot 저장과 읽기 전용 조회·복원 | Task 0 |
| Task 3 (#120) | 설정·Replay·복원 UI와 오류 표시 | Task 0, API 연동은 Task 1 |
| Task 4 (#121) | Runtime·LLM·Tick 호출 0회 검증과 guard | Task 0, 통합 검증은 Task 1 |
| Task 2 (#119) | 인수·누적 회귀 및 최종 증빙 | Task 1·3·4 |

모든 Task 브랜치는 `feature/issue-116-slice6-base`에서 분기하고 Task PR의 base도 같은 브랜치로 지정한다.

각 Task의 실행 명령과 PASS 결과는 해당 Task PR의 `테스트 / 확인 내용`에 기록하고 Parent #116에 링크를 남긴다. Task 2는 Task 1·3·4의 증빙을 취합해 최종 인수·누적 회귀 결과를 같은 위치에 기록한다.

## 6. Task 0 결정 사항

1. **복원 방식**: Snapshot 상태를 읽기 전용으로 재구성하며 Simulation과 실행 이력을
   변경하거나 새 분기를 생성하지 않는다.
2. **Snapshot 생성 단위**: Tick 0과 모든 Tick의 batch transaction 안에서 Snapshot을
   저장하고 전체 결과를 한 번에 commit한다.
3. **Snapshot 상태 범위**: 4.2의 전체 범위를 불변 payload로 저장한다.
4. **설정 범위**: `event_frequency`, `event_impact`, `magic_frequency`, `magic_impact`,
   `magic_enabled`, User Persona 및 초기 seed를 설정 버전에 저장하고 Snapshot에
   보존한다. 일반 Event 설정만 실행 중 변경할 수 있고 Magic·Persona 설정은
   시작 후 잠근다. 초기 seed는 생성 시 실제 사용한 값을 유지한다.
5. **보존 정책**: MVP에서는 Snapshot을 기간·개수 제한 없이 보존한다.
6. **동일 Tick 정렬 기준**: Tick 안의 원본 출력 순서를 보존하는 별도 sequence를 저장한다.
7. **시점 복원 부작용**: 새 Simulation·Tick·실행 계보 생성과 원본 변경은 모두 금지한다.
8. **Runtime 결과**: 원본 Replay·감사용 payload로 보존하고 조회 시에만 사용한다.
9. **격리수준 책임**: Tick 시작 world state의 `REPEATABLE READ` 적용은 Tick Engine
   경계에서 담당하고, Task 2 누적 PostgreSQL 회귀 테스트에서 검증한다.

## 7. Task 0 완료 기준

- [x] 6장의 모든 항목이 확정되어 있다.
- [x] Task 1·3·4가 동일한 설정·Snapshot·Replay 계약을 참조한다.
- [x] Replay 무재실행 규칙과 실패 방식이 명확하다.
- [x] Snapshot 저장 transaction과 읽기 전용 복원 경계가 명확하다.
- [x] API 오류 상태가 확정되어 있다.
- [x] Task별 테스트 증빙 위치와 최종 통합 순서가 합의되어 있다.
