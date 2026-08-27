---
title: MVP Tick 시간 및 Event 발생 정책
status: draft
updated: 2026-08-27
visibility: public
source:
  - docs/02-domain/time-and-space.md
  - docs/02-domain/events.md
  - docs/03-system-design/tick-engine.md §2
  - docs/03-system-design/event-master.md §4.3
  - "GitHub Issue #182 ([Feature] 1단계 미포함 MVP 기능 백엔드 지원)"
관련 PRD: F4-04(이벤트 파라미터 설정) · F5-01(Tick 상태 표시) · F5-03(밤 시간 스킵)
---

# MVP Tick 시간 및 Event 발생 정책

> **이 문서가 구현 단일 계약이다.** 아래 §9에 열거한 기존 문서의 직접 충돌 조항은
> 구현 단계에서 이 스펙에 맞춰 정합화한다. 그 밖의 기존 문서 내용은 이 스펙이
> 변경하지 않는다.

## 1. 목적

MVP 스코프에는 있으나 Slice 0~7에서 구현되지 않은 세 가지 백엔드 규칙을 채운다.

1. Tick 시간 구조(MORNING / AFTERNOON / EVENING · 24분 = 1일)를 계약으로 고정한다.
2. 저녁 블록 이후 야간을 스킵하고 다음 날 아침으로 전환하는 수동 경로를 만든다.
3. 사용자가 설정한 `event_frequency` / `event_impact` 파라미터가 실제 동적 Event
   생성 빈도와 효과 크기에 반영되게 한다.

## 2. 범위

**포함**

- `tick_position()` 계약 회귀 테스트 (day / block 파생 규칙 고정)
- `Simulation.night_waiting` boolean 필드 추가 및 Alembic 마이그레이션
- EVENING Tick batch commit 성공 시 `night_waiting = true` 설정
- `advance_manual_tick`이 시작 시 `night_waiting == true`이면 야간 전환을 먼저 수행
  하도록 통합 (§4.2)
- `POST /simulations/{simulation_id}/night/skip` 엔드포인트 + 야간 전환 서비스
  (수동·자동 경로 공용)
- `advance_manual_tick`이 Tick 시작 시 해당 simulation의 최신 `SimulationConfig`
  (`event_frequency` / `event_impact` / `version`)를 읽어 Tick 종료까지 고정 사용
- Event Master 동적 Event 후보 생성에 `event_frequency` 빈도 판정(확률 · 일일 상한 ·
  Tick당 상한) 반영
- Policy Engine / Event Master에 `event_impact` 효과 강도 배율 · importance · 참여
  Agent 상한 · 쿨다운 · Reflection 적격 · 당일 high 참여 제외 반영
- 각 Tick 스냅샷에 그 Tick에서 고정 사용한 `config_version` 기록
  (`SimulationSnapshot.config_version` 재사용, 단 "종료 시 latest"가 아니라 "시작 시
  고정값"으로 변경)
- Event 파라미터 생명주기(Draft `PUT /parameters` ↔ 실행 중 `PATCH /parameters`)와
  Event 정책의 연결 명문화 (§4.5) — 기존 3.11 API 계약은 코드로 바꾸지 않음
- 구현 단계에서 함께 갱신: `docs/00-start-here/what-is-pending.md` · `events.md` ·
  `time-and-space.md`의 "이벤트 발생 빈도" 미정 표기 (§9)
- Slice 0~7 회귀 테스트 무결

**제외**

- APScheduler 자동 Tick 진행 및 자동 야간 타이머 → §8-1
- 야간 회복 Policy의 상태값 변경(피로도 / 스트레스 회복 등) 및 수치 → §8-2
- 블록별 실제 시각 범위(아침 08:00~ 등) 정의 및 블록별 Event 매핑 — MVP 기계 동작에
  불필요, `what-is-pending.md`의 해당 행은 그대로 둔다
- Magic Layer 특수 사건의 빈도 / 영향도(`magic_frequency` / `magic_impact`) — Issue
  #182의 다른 하위 작업
- FE 화면(F4-04 / F5-03 UI)

## 3. 입력 / 출력

| 항목 | 설명 |
|---|---|
| 입력 (Tick) | `current_tick`, `simulation.status`, `simulation.night_waiting`, Tick 시작 시 고정한 `SimulationConfig`(event_frequency / event_impact / version), 예정 Event 목록, 활성 Agent 요약, 당일 동적 Event·high 참여 이력(기존 `events`/`event_participants` 조회) |
| 출력 (Tick) | 동적 Event 0~1개(예정 Event와 합쳐 Tick당 ≤ 3), 스냅샷에 기록된 적용 `config_version` |
| 입력 (night/skip) | `simulation_id` (path), 본문 `{}` |
| 출력 (night/skip) | `{ "data": { "id", "status", "current_day", "current_tick" } }` — `current_tick` 불변 |
| 저장 | `simulations.current_day`, `simulations.night_waiting`, `simulation_snapshots.config_version` |

### 3.1 night/skip 상태 전이 · 응답 매트릭스

| 조건 (순서대로 평가) | 응답 |
|---|---|
| 미인증 | 401 UNAUTHORIZED |
| Simulation 없음 | 404 RESOURCE_NOT_FOUND |
| 소유자 아님 | 403 FORBIDDEN |
| `status ∈ {ready, completed, failed}` | 422 BUSINESS_RULE_VIOLATION |
| Tick 실행용 advisory lock 획득 실패 (대개 Tick 진행 중, 드물게 동시 night/skip) | 409 CONFLICT |
| `night_waiting == true` | **야간 전환 수행** → 200 |
| `night_waiting == false` **且** `current_tick > 0` **且** `current_tick % 3 == 0` **且** `current_day == derived_day + 1` (이미 전환 완료 = 멱등 재호출) | 상태 변경 없이 200 |
| 그 외 (`night_waiting == false` 이고 위 멱등 조건 불성립: 하루 중간, 또는 EVENING 직후인데 `night_waiting`이 false인 상태 불일치) | 409 CONFLICT (상태 불일치 시 경고 로그) |

`derived_day = ((current_tick - 1) // 3) + 1` (= `tick_position(current_tick)`의 day).

## 4. 핵심 동작

### 4.1 Tick 시간 구조 (기구현 — 계약 고정만)

- `tick_position(n) → (day, block)`:
  `day = ((n - 1) // 3) + 1`, `block = [MORNING, AFTERNOON, EVENING][(n - 1) % 3]`
- 1 Tick = 1 블록 = 8분, 1일 = 3 Tick = 24분
- `advance_manual_tick`은 이 파생값으로 `current_tick` / `current_day`를 갱신한다
  (파생 규칙 자체는 변경 없음).
- 신규: 경계값(3 → 1일 EVENING, 4 → 2일 MORNING, 6 → 2일 EVENING, 7 → 3일 MORNING …)
  과 `tick_position(0)` / 음수 → `ValueError` 를 회귀 테스트로 고정한다.

### 4.2 야간 스킵 / 다음 날 전환 (신규)

**야간 대기 상태 (`Simulation.night_waiting`)**

- 야간 대기 여부는 `night_waiting` 필드로만 판단한다. 블록 값만으로 추론하지 않는다.
- 불변식: EVENING Tick(`current_tick % 3 == 0`, `current_tick > 0`)의 batch commit이
  성공하면 **같은 transaction에서** `night_waiting = true`로 설정한다.
- MORNING / AFTERNOON Tick commit은 `night_waiting`을 건드리지 않는다 (항상 false).
- 야간 전환(수동 skip 또는 `advance_manual_tick` 통과) 성공 시 `night_waiting = false`.

**야간 전환 로직 (수동·자동 공용 서비스)**

1. Agent Runtime · Event Master · Magic Layer를 호출하지 않는다.
2. `current_tick`을 변경하지 않는다.
3. `current_day += 1`.
4. `night_waiting = false`.
5. 다음 블록은 자연히 MORNING이다 (블록은 `tick_position(current_tick + 1)`로 파생,
   EVENING 다음 Tick = MORNING). 블록을 별도 컬럼에 저장하지 않는다.
6. **MVP에서는 야간 회복을 수행하지 않는다 — Agent 상태값(피로도 / 스트레스 등)을
   변경하지 않는다.** 회복 훅을 구현하지 않아도 된다 (§8-2, 후속).

**`POST /simulations/{simulation_id}/night/skip`**

- 권한: 로그인 사용자, 본인 소유 Simulation.
- Tick과 동일한 advisory lock
  (`pg_try_advisory_xact_lock(hashtextextended(simulation_id, 0))`)을 시도하고, 실패
  시 409를 반환한다.
- §3.1 매트릭스에 따라 200 / 409 / 422를 반환한다. 200(전환 수행) 시 commit 성공 후
  WebSocket `SIMULATION_STATUS_UPDATED`를 발행한다 (payload: `id`, `status`,
  `current_day`, `current_tick`). 멱등 200(상태 변경 없음)은 재발행하지 않는다.

**`advance_manual_tick` 통합**

- `advance_manual_tick`은 `night_waiting`으로 차단되지 않는다.
- 실행 시작 시 `night_waiting == true`이면 위 "야간 전환 로직"을 같은 transaction에서
  먼저 수행한 뒤(= `current_day += 1`, `night_waiting = false`, 회복 no-op) 다음
  (MORNING) Tick 본문을 진행한다. `night_waiting == false`이면 야간 전환을 건너뛴다.
- EVENING Tick의 다음 Tick은 `tick_position().day`가 이미 +1이므로, 순차 advance만
  하는 기존 흐름의 `current_tick` / `current_day` 진행값은 이 통합 후에도 동일하다
  (기존 Slice 회귀 무결).

### 4.3 Event 발생 빈도 정책 (신규)

| `event_frequency` | 동적 Event 후보 생성 확률 | 하루 최대 동적 Event | Tick당 최대 동적 Event |
|---|---:|---:|---:|
| low | 25% | 1 | 1 |
| medium (기본) | 50% | 2 | 1 |
| high | 75% | 2 | 1 |

**적용 대상**: `event_frequency`는 **동적 일반 Event**(GROUP_PROJECT / MEETING)의
후보 생성에만 적용한다. 예정 Event(CLASS / EXAM / MT / FESTIVAL / STUDENT_COUNCIL)는
학사 일정에서 활성화되며 `event_frequency`와 무관하게 항상 생성된다. 마법 특수
사건에는 적용하지 않는다.

**Tick별 판정 (아래 순서, 모두 만족해야 동적 Event 1개 생성)**

1. Tick 시작 시 예정 Event를 먼저 확정한다.
2. **예정 Event 수 < 3** — 예정 Event가 3개 이상이면 동적 Event를 생성하지 않는다.
   (MVP 픽스처는 예정 Event 1개(CLASS)이므로 이 분기는 방어적 조항이다.)
3. **당일 동적 Event 누적 수 < 일일 상한** — 같은 `current_day`에 이미 확정된 동적
   Event 수가 `event_frequency`의 하루 최대(1 / 2 / 2)에 도달했으면 그 날 남은 블록
   에서는 확률 판정을 하지 않는다.
   - 일일 상한은 **동적 Event에만** 적용한다. 예정 Event는 카운트하지 않는다.
   - `high`도 하루 최대 2회다. frequency가 커지면 확률만 증가하고 상한은 최대 2회다.
   - 당일 누적 수는 `events` 테이블에서 `source = 'event_master'` 且 `event_type ∈
     {GROUP_PROJECT, MEETING}` 且 `tick_number`가 당일 범위 `[3*(current_day-1)+1 ..
     current_tick)` 인 행 수로 구한다 (별도 저장소 없음). `current_day`가 바뀌면
     (정상 진행 또는 night/skip) 당일 범위가 이동하므로 카운터는 자연히 리셋된다.
4. **확률 통과** — 시드 문자열 `f"{simulation_id}:{tick_number}:{config_version}"`의
   안정적 해시(예: SHA-256 선행 8바이트를 정수로)로 초기화한 `random.Random`에서
   draw 1회를 뽑아 `draw < 확률`이면 통과한다. 같은 세 값이면 항상 같은 결과여야
   한다. 프로세스 간 불안정한 파이썬 내장 `hash()`는 쓰지 않는다.
5. 통과하면 Event Master가 허용 타입(GROUP_PROJECT / MEETING) 하나와 참여 Agent ·
   장소를 결정해 동적 Event 후보 1개를 만든다. 후보 조건(참여 인원 최소 2명 등)을
   만족하지 못하면 그 Tick에는 동적 Event가 없다.

**상한 관계**: 동적 Event는 Tick당 최대 1개. 예정 Event 수 + 동적 Event 수는 기존
계약에 따라 Tick당 3개를 넘지 않는다. MVP에서는 예정 1 + 동적 ≤ 1 이므로 실질 합계
≤ 2다. Issue #182의 "하루 1~2회"는 기본값 medium(하루 최대 2) · low(하루 1)와 정합
한다.

### 4.4 Event 영향도 정책 (신규)

| `event_impact` | importance | 효과 강도 배율 | 동적 Event 참여 Agent 상한 | 동일 참여자 쿨다운 | Reflection 적격 |
|---|---:|---:|---:|---:|---|
| low | 30 | 0.5 | 2 | 없음 (0 Tick) | 아니오 |
| medium (기본) | 50 | 1.0 | 4 | 1 Tick | 아니오 |
| high | 80 | 1.5 | 5 | 3 Tick | 예 |

**효과 강도 배율**

- Policy Engine은 Event 유형별 기본 delta(`EVENT_BASE_EFFECTS`)에 배율을 곱한 뒤
  `round(base_delta × 배율)` (파이썬 내장 `round`, 0.5는 가장 가까운 짝수)로 정수화
  하고, 그다음 기존 metric별 허용 범위로 clamp한다.
- 적용 지점: `build_event_effect_candidates`
  (`app/simulation/policy/registries/event_policy.py`)에서 `EVENT_BASE_EFFECTS`를
  소비하는 위치. clamp는 기존 Conflict Resolver 단계 그대로.
- 배율은 `EVENT_BASE_EFFECTS`의 모든 항목(예정 CLASS/EXAM/MT/FESTIVAL 및 동적
  GROUP_PROJECT/MEETING)에 적용한다. 기본값 medium은 배율 1.0이므로 기존 효과와
  동일하다 (회귀 무결).
- 마법 특수 사건의 typed signal 경로에는 배율을 적용하지 않는다.

**importance · 참여 Agent 상한**

- `importance`(30 / 50 / 80)와 참여 Agent 상한(2 / 4 / 5)은 **동적 Event**에만
  적용한다. Event Master가 동적 Event 후보를 만들 때 importance를 이 표로 설정하고,
  참여 Agent 목록을 상한까지만 남긴다(정렬은 기존 코드대로 `agent_id` 오름차순).
- 상한 적용은 아래 "당일 high 참여 제외" · "쿨다운" 제외 후에 수행한다. 제외 후
  남은 인원이 타입 최소 인원(2명) 미만이면 그 Tick에 동적 Event를 만들지 않는다.
- 예정 Event의 importance는 기존대로 학사 일정의 `impact_level`이 결정한다 (변경
  없음).

**Reflection 적격**

- 기존대로 `event.importance >= 70` (`REFLECTION_IMPORTANCE_THRESHOLD`)으로 판정한다.
- 동적 Event importance는 `event_impact`가 결정하므로 `event_impact = high`(80)인
  동적 Event만 적격이고, low(30) / medium(50)은 비적격이다.

**동일 참여자 쿨다운 — 정확한 정의**

- **무엇을 제한하는가**: 새로 생성되는 **동적 일반 Event의 참여 Agent 선정**만
  제한한다. Event 생성 자체를 막지 않고, 특정 Agent를 그 후보의 참여자에서 제외
  한다. GROUP_PROJECT 쿨다운과 MEETING 쿨다운은 `event_type`별로 독립이다.
- **규칙**: 새 동적 Event 후보의 타입이 `T`(GROUP_PROJECT 또는 MEETING)이고 현재
  Tick이 `t`일 때, Agent `A`가 타입 `T`의 동적 Event에 tick `t'`에 참여한 이력이
  있고 그 Event의 `event_impact` 쿨다운 `N`(low 0 / medium 1 / high 3)에 대해
  `t - t' < N` 이면, `A`를 새 후보의 참여자에서 제외한다.
- **적용 단계**: Event Master의 참여 Agent 선정 단계. (생성 확률 판정 이후, 참여
  Agent 상한 적용 이전.)
- **제한 범위**: 동적 일반 Event(GROUP_PROJECT / MEETING)만. **예정 Event
  (CLASS/EXAM/MT/FESTIVAL/STUDENT_COUNCIL)는 쿨다운의 영향을 받지 않으며, 쿨다운
  기간에도 항상 정상 활성화된다.** 마법 특수 사건도 무관하다.
- **impact level 기준**: 쿨다운 길이 `N`은 **직전에 참여한 그 Event의 impact
  level**이 정한다. 새 후보의 impact level과는 무관하다.
- **측정 단위**: `current_tick` 차이. 야간 전환은 `current_tick`을 증가시키지 않으
  므로 쿨다운은 밤을 사이에 두고 자연히 이어진다.
- **이력 출처**: `events` + `event_participants` 조회(`source = 'event_master'`,
  `event_type ∈ {GROUP_PROJECT, MEETING}`, 최근 `max(N)=3` Tick). 별도 저장소 없음.

**동일 Agent 당일 high 참여 제외**

- Agent `A`가 같은 `current_day`에 `event_impact = high` 동적 Event에 이미 참여했다면,
  추가 high 동적 Event 후보의 **참여자에서 `A`만 제외**한다. Event를 medium으로
  하향하지 않는다.
- 당일 high 참여 이력은 `events`(`event_type ∈ {GROUP_PROJECT, MEETING}`,
  `importance = 80`, 당일 tick 범위) + `event_participants` 조회로 판정한다.
- `high × high` 조합 자체는 허용한다 — 제한은 이 "당일 1회" 규칙으로만 건다.

### 4.5 파라미터 생명주기 (API ↔ config_version)

Event 파라미터는 `event_frequency`, `event_impact` 두 개다. 허용값 `low` / `medium`
/ `high`, 기본값은 둘 다 `medium`. API는 값을 **저장**하고, Tick / Event Master /
Policy Engine이 그 값을 §4.3 · §4.4 정책으로 **적용**한다.

기존 API 계약(3.11 API 명세, 라우트 `PUT` / `PATCH /simulations/{simulation_id}/
parameters`)은 이 스펙에서 코드로 바꾸지 않는다 — 아래는 그 계약과 Event 정책의
연결을 명확히 하는 것이다.

#### 4.5.1 Simulation 시작 전 — Draft(`ready`)

- 라우트: `PUT /simulations/{simulation_id}/parameters`
- 본문: `event_frequency`, `event_impact`, `magic_enabled`
  (`SimulationConfigPutRequest`, 추가 필드 금지)
  ```json
  { "event_frequency": "medium", "event_impact": "medium" }
  ```
  (Magic Layer 관련 필드·규칙은 기존 3.11 계약 그대로 유지한다. 이 스펙은
  `event_frequency` / `event_impact` 연결만 명확히 한다.)
- 처리:
  - `ready` 상태에서 Event 파라미터를 저장 / 변경할 수 있다.
  - 저장할 때마다 새 `SimulationConfig` version을 생성한다(append-only).
  - Simulation 시작 시점부터 그 config를 사용한다.
  - 시작 후에는 §4.5.3의 Tick별 `config_version` 정책을 따른다.

#### 4.5.2 Simulation 실행 중 — `running` / `paused`

- 라우트: `PATCH /simulations/{simulation_id}/parameters`
- 본문: `event_frequency`, `event_impact` 만 (`SimulationConfigPatchRequest`, 추가
  필드 금지)
  ```json
  { "event_frequency": "high", "event_impact": "low" }
  ```
- 변경 가능 필드: `event_frequency`, `event_impact`. **`magic_enabled` 및 Magic
  Layer 파라미터는 이 PATCH로 바꾸지 않는다**(기존대로 최신 config 값을 승계).
- 처리 규칙:
  1. 요청이 성공하면 새 `SimulationConfig` version을 생성한다.
  2. 현재 실행 중인 Tick이 있으면 그 Tick은 **Tick 시작 시 고정한 기존
     `config_version`**으로 끝까지 실행한다.
  3. 변경된 `event_frequency` / `event_impact`는 **다음 Tick부터** 적용한다.
  4. Tick 중간에 설정이 부분적으로 바뀌지 않는다(§4.5.3의 원자적 고정).
  5. Tick 시작 시 `SimulationConfig`를 snapshot하고 `config_version`을 고정한다.
  6. Tick 결과(스냅샷)에는 실제 적용된 `config_version`을 기록한다.
  7. `effective_tick` = 변경된 설정이 처음 적용되는 다음 Tick 번호.
     - 변경 시점에 진행 중 Tick이 없으면 `effective_tick = current_tick + 1`.
     - 진행 중 Tick(번호 `t`)이 있으면 그 Tick은 기존 version으로 끝나고
       `effective_tick = t + 1`.
  8. **Tick이 실행 중이라는 이유만으로 PATCH를 409로 거부하지 않는다.** PATCH는
     version만 추가하고, 적용은 다음 Tick 경계에서 일어난다.
  9. `running` / `paused` 이외 상태 및 그 밖의 에러 규칙은 기존 3.11 API 계약을
     따른다(`completed` / `failed`는 `save_config`가 잠금 →
     `SIMULATION_SETTINGS_LOCKED`).

#### 4.5.3 Tick 적용 (config_version 고정)

| 상황 | 처리 |
|---|---|
| Tick 시작 | 그 simulation의 최신 `SimulationConfig`를 1회 읽어 `(event_frequency, event_impact, version)`를 Tick 종료까지 고정. §4.3 확률 시드와 §4.4 배율에 이 값을 사용 |
| Tick 실행과 PATCH 경합 | 현재 Tick은 시작 시 고정한 version으로 완료, 변경값은 `effective_tick`부터 |
| Tick 종료 | 스냅샷에 "시작 시 고정한" `config_version`을 기록 |
| Replay | 스냅샷의 `config_version`으로 원본 `SimulationConfig` 행을 재조회해 동일 정책 재현. Event Master · LLM 재호출 없음 |

- **신규 wiring**: `advance_manual_tick`은 현재 `SimulationConfig`를 읽지 않는다. 이
  스펙에서 Tick 시작 시 `SimulationConfigRepository.latest()`를 1회 읽어 고정한다.
- **스냅샷 기록 변경**: `SimulationSnapshotService.create_snapshot`은 현재 "종료
  시점 `latest`"를 스냅샷에 넣는다. 이를 "Tick 시작 시 고정한 config"를 받아 넣도록
  바꾼다. 이래야 진행 중 PATCH 변경분이 현재 Tick 스냅샷에 새지 않는다.
- `SimulationConfig`는 append-only(`create_version` = `max(version) + 1`)라 과거
  version 행이 보존된다 → Replay가 스냅샷의 `config_version`으로 원본을 재조회할 수
  있다.
- API 레이어(`save_config`)는 이미 `ready` / `running` / `paused`에서만
  `event_frequency` / `event_impact` 변경을 허용한다. 이 스펙은 API 레이어를 바꾸지
  않는다.

#### 4.5.4 흐름 요약

```
[Simulation 시작 전]
  ready
   → PUT /simulations/{simulation_id}/parameters
   → event_frequency / event_impact 저장 (새 config_version)
   → Simulation 시작
   → 해당 config_version 사용

[Simulation 실행 중]
  running / paused
   → PATCH /simulations/{simulation_id}/parameters
   → event_frequency / event_impact 변경 (새 config_version)
   → 현재 Tick은 시작 시 고정한 기존 config_version으로 완료
   → effective_tick(= 다음 Tick)부터 새 설정 적용
```

## 5. 경계 조건

- `tick_position(0)` 및 음수 → `ValueError`.
- night/skip은 `night_waiting == true`에서만 상태를 전환한다. 그 외는 §3.1 매트릭스
  (200 멱등 / 409 / 422).
- 야간 전환(수동·자동 공용)은 `current_tick`을 절대 변경하지 않는다.
- Tick 실행용 advisory lock을 잡지 못하면 night/skip은 항상 409.
- 상태 불일치(EVENING 직후인데 `night_waiting == false`, 且 전환 완료 흔적 없음)는
  409 + 경고 로그. "이미 처리됨"으로 오인해 200을 주지 않는다.
- 예정 Event만으로 Tick당 3개면 동적 Event는 0개.
- 예정 Event는 `event_frequency = low` · 쿨다운 기간에도 항상 활성화된다.
- 일일 동적 Event 상한 도달 후 그 날 남은 블록에서는 확률 판정을 건너뛴다.
- `current_day` 변경 시 "당일 동적 누적" · "당일 high 참여" 판정 범위가 새 날로
  이동한다.
- 진행 중 Tick의 결과는 그 Tick 시작 시 고정한 `config_version`으로만 계산된다.
- 동일 metric UP / DOWN 충돌, stale before 등 기존 Policy Engine 계약은 유지된다
  (이 스펙은 배율 → 정수화 → clamp 순서만 추가).

## 6. 데이터 구조

### 6.1 `Simulation.night_waiting` (신규 컬럼)

| 항목 | 값 |
|---|---|
| 컬럼 | `night_waiting BOOLEAN NOT NULL DEFAULT false` |
| 마이그레이션 | Alembic revision 신규. 기존 행은 `server_default = false`로 백필 (기존 시뮬레이션은 야간 대기 아님으로 간주. EVENING 직후였던 기존 sim은 §3.1의 409 경로로 떨어지며, `advance_manual_tick` 통합 경로로 다음 Tick 시 정상화된다.) |
| 쓰기 시점 | EVENING Tick commit 성공 → `true`. 야간 전환(수동 skip / advance 통합) 성공 → `false`. |

### 6.2 재사용 (스키마 변경 없음)

- `SimulationConfig`: `event_frequency` / `event_impact`(`low|medium|high`), `version`
  (append-only)
- `SimulationSnapshot.config_version`: Tick별 "시작 시 고정" 파라미터 version
- `EVENT_BASE_EFFECTS` (`event_policy.py`): 효과 강도 배율 적용 지점
- `REFLECTION_IMPORTANCE_THRESHOLD = 70` (`event_magic_phase.py`): Reflection 적격
  임계값
- `events` / `event_participants`: 당일 동적 누적 · 쿨다운 · 당일 high 참여 이력 조회

## 7. 완료 기준

- [ ] `tick_position` 경계값 · 예외 회귀 테스트
- [ ] Alembic 마이그레이션 up / down · 기존 데이터 `night_waiting = false` 백필 검증
- [ ] EVENING Tick commit 성공 시 `night_waiting = true`, MORNING / AFTERNOON commit은
      변화 없음
- [ ] `POST /night/skip` §3.1 매트릭스 전 케이스: 200(전환) / 200(멱등, 무변경) /
      401 / 403 / 404 / 409(하루 중간) / 409(advisory lock) / 409(EVENING 직후 상태
      불일치) / 422(`ready`/`completed`/`failed`)
- [ ] 야간 전환이 `current_tick` 불변 · `current_day + 1` · `night_waiting = false` ·
      Agent Runtime / Event Master / Magic Layer 미호출 · `agent_states` 무변경
- [ ] `SIMULATION_STATUS_UPDATED` 발행 (전환 200에서만, commit 성공 후)
- [ ] `advance_manual_tick`이 `night_waiting == true`에서 야간 전환을 먼저 수행하고
      MORNING Tick 진행, 순차 advance 시 `current_tick`/`current_day` 진행값이 기존과
      동일
- [ ] `event_frequency` low / medium / high 별 확률 · 일일 상한(1 / 2 / 2) · Tick당
      상한(1) — 같은 `(simulation_id, tick_number, config_version)`이면 결정론적으로
      동일 결과
- [ ] 예정 Event ≥ 3 → 동적 Event 0개 / 예정 Event는 `event_frequency = low` ·
      쿨다운 기간에도 항상 활성
- [ ] 일일 상한 도달 후 같은 날 추가 동적 Event 미생성, `current_day` 변경 시 판정
      범위 이동
- [ ] `event_impact` 별 importance(30/50/80) · 배율(0.5/1.0/1.5) · 동적 참여 상한
      (2/4/5) · Reflection 적격(high만)
- [ ] `round(base_delta × 배율)` 후 metric 허용 범위 clamp 검증 (medium ×1.0은 기존
      값과 동일)
- [ ] 쿨다운: 타입별 독립, `t - t' < N`(N = 직전 참여 Event impact의 0/1/3),
      해당 Agent만 참여 제외, 제외 후 2명 미만이면 동적 Event 미생성, 예정 Event는
      영향 없음
- [ ] 동일 Agent 당일 2회차 high 동적 Event 후보에서 해당 Agent만 제외 (Event 유지,
      하향 없음)
- [ ] Draft(`ready`) `PUT /parameters` → 새 `config_version` 생성, 시작 시점부터 사용
- [ ] `running` / `paused` `PATCH /parameters` → 새 `config_version`, 현재 Tick 불변,
      `effective_tick`(다음 Tick)부터 적용, Tick 실행 중이어도 409로 거부하지 않음
- [ ] `PATCH`로 `magic_enabled` / Magic 파라미터 변경 불가 (기존 계약)
- [ ] Tick 스냅샷에 "시작 시 고정" `config_version` 저장 · Replay 재현
- [ ] `what-is-pending.md` / `events.md` / `time-and-space.md` 갱신 (§9)
- [ ] Slice 0~7 회귀 · Ruff · Mypy 통과

## 8. 후속 이슈 (이번 스펙 범위 밖 — 별도 정의)

1. **자동 야간 전환 / APScheduler** — 이번 MVP는 수동 `POST .../night/skip` +
   `advance_manual_tick` 통합만 구현한다. 야간 대기 시간 설정값은 도입하지 않는다.
   자동 전환 추가 시 §4.2 "야간 전환 로직"을 그대로 재사용한다.
2. **야간 회복 Policy 수치** — 야간 스킵 시 피로도 / 스트레스 등 회복량. MVP에서는
   정의하지 않으며 야간 전환은 상태값을 변경하지 않는다(회복량 0). 별도 후속 이슈
   에서 정의하고, 그때 §4.2 "야간 전환 로직" 안에 회복 단계를 추가한다.

## 9. 기존 문서 정합화 대상 (이 스펙과 직접 충돌하는 조항만)

이 Feature Spec을 구현 계약 단일 기준으로 삼는다. 구현 단계에서 아래만 이 스펙에
맞춘다. 그 외 기존 문서 문장은 수정하지 않는다.

**갱신 (이 스펙 완료 기준에 포함)**

| 문서 | 현재 | 이 스펙 기준으로 |
|---|---|---|
| `docs/00-start-here/what-is-pending.md` | "이벤트 발생 빈도 \| 미정" 행 | 확정으로 이동. 비고: "Issue #182 — `event_frequency` low/medium/high = 하루 최대 1/2/2, Tick당 1. 계약: `docs/04-feature-specs/mvp-tick-event-policy.md`". "tick 3블록 시간대 상세" 행은 그대로 둔다 (블록 시각 범위 · 블록별 Event 매핑은 이 스펙 범위 밖). |
| `docs/02-domain/events.md` | "### 사건 발생 빈도 > **미정** — Time Tick 최종 확정과 함께 결정 예정" | 확정 문구로 교체 + 이 Feature Spec 참조. 사건 목록·분류 표는 변경 없음. |
| `docs/02-domain/time-and-space.md` | "> **미정**: 이벤트 발생 빈도 → `what-is-pending.md`" (Tick 정의 아래) | 확정 참조로 교체. "> **미정**: 각 블록 세부 시간 범위 및 Event 매핑" 주석은 그대로 둔다. |

**정합화 필요 (별도 후속 — 이 스펙이 계약이며, 아래 문서를 이 스펙에 맞춘다)**

| 문서 | 현재 | 충돌 |
|---|---|---|
| `docs/03-system-design/event-master.md` §4.3 빈도 표 | `high` 하루 최대 **3** | 이 스펙: `high` 하루 최대 **2**. (확률 25/50/75%, Tick당 1은 동일.) |
| `docs/03-system-design/event-master.md` §4.3 영향도 불릿 + 검증 P6 | "동일 Agent는 하루에 high 영향도 Event 최대 1회 … 초과 후보는 **medium으로 낮추거나 생성하지 않는다**" | 이 스펙: 초과 시 **해당 Agent만 참여 후보에서 제외**, Event를 medium으로 하향하지 않음. |
| `docs/03-system-design/event-master.md` §4.3 쿨다운(P4) | "동일 유형·조합 후보 제외" (범위가 느슨함) | 이 스펙 §4.4로 정밀화: 동적 Event 참여자 선정 단계, `event_type`별 독립, 예정 Event 무관, `N` = 직전 참여 Event impact의 0/1/3 Tick. |

**보고만 (이 스펙의 문서 갱신 범위 밖 — 별도 처리 필요)**

- `docs/03-system-design/architecture.md:88` "밤 시간대: tick 번호만 전진"이
  `tick-engine.md:40` "Tick 번호 증가 없이 current_day + 1"과 모순. 이 스펙은
  tick-engine.md(v2.2, 사용자 확인)를 따른다.
- `docs/02-domain/world-setting.md:246` "저녁 블록 이후 다음 날 아침으로 자동 전환"
  은 자동 전환을 전제하나 이번 MVP는 수동 `night/skip` + `advance_manual_tick` 통합
  만 구현한다 (§8-1). 자동 전환은 후속.

## 10. 관련 문서

- `docs/02-domain/time-and-space.md`, `docs/02-domain/events.md`,
  `docs/02-domain/agents.md`
- `docs/03-system-design/tick-engine.md`, `docs/03-system-design/event-master.md`,
  `docs/03-system-design/policy-engine.md`
- `docs/04-feature-specs/FR-01-agent-state-policy.md`,
  `docs/04-feature-specs/slice-5-integration.md`
- `docs/00-start-here/what-is-pending.md`
- GitHub Issue #182

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
|---|---|---|
| 0.1.0 | 2026-08-27 | 최초 초안. Tick 시간 구조 계약 고정, 야간 스킵 / 다음 날 전환(`night_waiting` 필드 + `POST /night/skip`), `event_frequency` 빈도 정책(하루 최대 2), `event_impact` 영향도 정책, config_version 생명주기 확정. |
| 0.2.0 | 2026-08-27 | 구현 전 최종 검토 반영. (1) night/skip 멱등성을 `current_day` vs `derived_day` 비교로 정의 — EVENING 직후 `night_waiting=false` 상태 불일치를 409로 분리, §3.1 상태·응답 매트릭스 추가. (2) `advance_manual_tick`이 `night_waiting=true`에서 야간 전환을 먼저 수행하도록 통합 정의(회귀 무결). (3) `event_impact` 쿨다운을 "동적 Event 참여자 선정 단계, `event_type`별 독립, 예정 Event 무관, N=직전 참여 impact의 0/1/3 Tick"으로 정밀화. (4) 빈도 확률 시드 알고리즘 · 배율 정수화 규칙(`round`) 명시. (5) config_version "Tick 시작 시 고정" wiring 및 스냅샷 기록 변경점 명시. (6) §9에 event-master.md §4.3 정합화 대상 3건 명시. |
| 0.3.0 | 2026-08-27 | §4.5를 API 생명주기로 확장. Draft(`ready`) `PUT /simulations/{id}/parameters`와 실행 중(`running`/`paused`) `PATCH /simulations/{id}/parameters`를 각각 명문화 — 본문 필드, 새 `config_version` 생성, 현재 Tick은 시작 시 고정 version으로 완료, `effective_tick`(= 다음 Tick) 정의, Tick 실행 중이라는 이유만으로 PATCH를 409로 거부하지 않음, `PATCH`는 `magic_enabled`/Magic 파라미터 미변경. §4.5.4 흐름 요약 블록 추가. §2·§7 항목 보강. 기존 3.11 API 계약은 코드로 변경하지 않음. |
