---
title: Magic Layer Agent 설계
source: confluence/05_TECH/magic-layer.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/9371768/Magic+Layer+Agent
status: approved
visibility: public
updated: 2026-07-28
source_updated: 2026-07-24
---

**기준 문서:** 시스템 아키텍처 (#8290305) · Tick Engine 스펙 (#12910622) · Policy Engine 설계 (#14090319)

> **2026-07-24 확정:** 특수 사건 발생 기준은 `world_state` 조건 기반으로 확정한다. 고정 확률 기반 생성은 사용하지 않는다.

---

## 0. 한 줄 정의

Magic Layer는 Tick Orchestrator를 위해 Event Master가 생성한 일반 이벤트를 마법 대학교 세계관으로 변환하고, 현재 세계 상태가 특정 임계값을 넘었을 때 조건에 맞는 마법 특수 사건을 생성한다. 특수 사건의 후보가 없을 경우에는 사건을 억지로 생성하지 않으며, 사건의 구체적인 수치 효과는 Policy Engine이 계산한다.

---

## 전제조건

| 항목 | 내용 |
| --- | --- |
| Event Master 출력 | 해당 tick에 Event Master가 생성한 `list[Event]` |
| world_state | 현재 tick의 세계 상태 스냅샷 |
| active_effects | 이전 특수 사건으로 인해 유지 중인 세계 상태 효과 |

`regular_events`가 빈 리스트인 경우 변환은 생략한다.

---

## 1. 존재 이유

### 1.1 해결하는 문제

Event Master는 일반 대학 생활 이벤트를 생성한다. 다음 마법 세계관 특수 사건은 별도의 판단 주체가 필요하다.

- 특정 장소에 피로가 누적되어 발생하는 폭발
- 저주에 걸린 학생과의 접촉으로 발생하는 저주 전파
- 스트레스가 장기간 누적된 학생의 실종
- 관계가 좋지 않은 학생들이 함께 참여한 의식의 실패
- 특별한 위험 조건이 없을 때 발견되는 새로운 마법

Magic Layer는 단순히 무작위로 사건을 생성하지 않는다.

```
세계 상태 → 발생 조건 판정 → 사건 후보 생성 → 사건 적용
```

---

## 2. 책임 경계

### 2.1 하는 일 (In Scope)

#### 일반 이벤트 변환
- Event Master가 생성한 이벤트를 마법 세계관으로 변환
- 매 tick 실행
- `title`, `description`, 필요한 경우 `location` 변환

#### 특수 사건 후보 판정

현재 `world_state`를 기준으로 사건별 발생 조건을 확인한다.

| 사건 | 발생 조건 |
| --- | --- |
| MAGIC_EXPLOSION | 특정 장소의 학생 피로도가 임계값 이상 |
| CURSE_SPREAD | 저주 상태 Agent와 접촉 |
| STUDENT_MISSING | Agent의 스트레스가 여러 tick 동안 임계값 이상 |
| RITUAL_FAILURE | 의식 참여자 수가 충분하고 관계 상태가 좋지 않음 |
| MAGICAL_DISCOVERY | 다른 특수 사건 조건이 충족되지 않은 경우 |

조건을 만족하지 않는 사건은 해당 tick의 후보에서 제외한다.

#### 특수 사건 생성
- 조건을 만족한 사건 후보를 생성
- 후보가 여러 개일 경우 우선순위 정책에 따라 하나를 선택
- 선택된 사건의 대상 Agent와 장소를 결정
- 사건의 효과 방향을 정의
- 지속 상태가 필요한 경우 상태 효과를 생성

#### 지속 상태 관리

```
CURSED
  → 저주 상태 유지
  → 접촉 시 CURSE_SPREAD 후보 발생

MISSING
  → 일정 기간 활동 불가
  → Agent Runtime 실행 대상에서 제외

RITUAL_EFFECT
  → 일정 tick 동안 특정 상태 효과 유지
```

### 2.2 하지 않는 일 (Out of Scope)

- 일반 대학 생활 이벤트 생성
- Agent의 행동 및 Intent 결정
- 관계 수치 직접 계산
- 피로도, 스트레스 등의 구체적인 수치 계산
- 조건을 만족하지 않는 사건의 강제 생성
- 지속 상태의 실제 수치 계산
- DB 직접 수정

Magic Layer는 **방향 정보만 제공**한다.

```json
{
  "effect": "trust",
  "direction": "decrease"
}
```

구체적인 감소량은 Policy Engine이 결정한다.

---

## 3. 인터페이스 계약

### 3.1 입력

| 항목 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| tick_number | int | ✅ | 현재 tick |
| world_state | WorldState | ✅ | 현재 세계 상태 |
| regular_events | list[Event] | ✅ | Event Master 이벤트 |
| active_effects | list[WorldEffect] | ✅ | 이전 사건으로 유지 중인 효과 |

### 3.2 출력

> 출력 구조: `converted_events[]`(event_type, title, description, participant_agent_ids, location, tick, source) + `special_events[]`(+ expected_effects.state_changes[], expected_effects.relationship_changes[], world_effects[])  
> `expected_effects` direction: `"increase"` / `"decrease"` — 숫자 delta 금지, 방향만 허용
```

---

## 3.2.1 특수 사건 발생 조건 상세

### MAGIC_EXPLOSION

특정 장소에 있는 학생들의 피로도가 임계값을 넘은 경우 후보가 된다.

```
location_fatigue >= FATIGUE_THRESHOLD

예: 마도공학 연구실에 있는 학생 3명 중
    2명 이상이 fatigue >= 80
    → MAGIC_EXPLOSION 후보
```

효과 방향:
- 참여 Agent의 `fatigue` 증가
- 참여 Agent의 `stress` 증가
- 사고 책임 관계가 형성된 경우 `trust` 감소

### CURSE_SPREAD

저주 상태인 Agent와 다른 Agent가 접촉했을 경우 후보가 된다.

```
CURSED_AGENT + CONTACT + TARGET_NOT_CURSED → CURSE_SPREAD 후보
```

효과 방향:
- 접촉 대상 Agent의 `satisfaction` 감소
- 접촉 대상 Agent의 `mood` 악화
- 저주 상태 추가
- 확산 경로에 있는 Agent 사이의 `tension` 증가 가능

저주 상태는 사건 발생 이후 여러 tick 동안 유지된다.

### STUDENT_MISSING

Agent의 스트레스가 단기간이 아니라 여러 tick 동안 지속적으로 높게 유지된 경우 후보가 된다.

```
stress >= STRESS_THRESHOLD
AND
최근 N개 tick 중 M개 이상에서 임계값 초과
→ STUDENT_MISSING 후보
```

단순히 현재 stress가 높다는 이유만으로 실종시키지 않는다.

효과 방향:
- 해당 Agent 상태를 `MISSING`으로 변경
- 일정 기간 활동 불가
- 친구 및 룸메이트의 `stress` 증가

실종 상태 관리:

```json
{
  "status": "MISSING",
  "start_tick": 120,
  "end_tick": 125
}
```

해당 기간 동안 Agent Runtime은 해당 Agent를 일반 행동 대상에서 제외한다.

### RITUAL_FAILURE

다음 조건을 모두 만족할 때 후보가 된다.

```
participant_count >= 최소 인원
AND
참여자 간 관계 상태가 좋지 않음
  (평균 trust 낮음 OR tension 높음)
→ RITUAL_FAILURE 후보
```

효과 방향:
- 참여자들의 `stress` 증가
- 참여자 간 `trust` 감소 가능
- 갈등이 심한 경우 `tension` 증가

LLM이 책임 소재와 구체적인 수치를 직접 결정하지 않는다.

### MAGICAL_DISCOVERY

다른 특수 사건 후보가 존재하지 않는 경우의 기본값이다.

```
MAGIC_EXPLOSION 후보 없음
AND CURSE_SPREAD 후보 없음
AND STUDENT_MISSING 후보 없음
AND RITUAL_FAILURE 후보 없음
→ MAGICAL_DISCOVERY 후보
```

단, `MAGICAL_DISCOVERY`도 무조건 생성할 필요는 없다. 전체적으로 특수 사건이 발생하지 않는 것이 자연스러운 상황이라면 해당 tick에 사건이 없을 수 있다.

---

## 3.2.2 사건 후보 우선순위

여러 사건 조건이 동시에 충족되는 경우:

```
STUDENT_MISSING
    ↓
CURSE_SPREAD
    ↓
MAGIC_EXPLOSION
    ↓
RITUAL_FAILURE
    ↓
MAGICAL_DISCOVERY
```

심각한 상태 변화가 발생할 가능성이 높은 사건을 우선한다.

---

## 3.2.3 효과 처리 원칙

**잘못된 방식 (숫자 직접 생성 금지):**

```json
{"trust": -13, "stress": 21}
```

**올바른 방식 (방향 정보만):**

```json
{
  "effects": [
    {"target": "trust", "direction": "decrease"},
    {"target": "stress", "direction": "increase"}
  ]
}
```

이후 Policy Engine이 사건 타입·Agent 현재 상태·관계 상태·사건 심각도·기존 효과를 바탕으로 실제 수치를 계산한다.

---

## 4. 동작 설계

### 4.1 처리 흐름

```
regular_events + world_state + active_effects 수신
        ↓
① 일반 이벤트 변환 → converted_events 생성
        ↓
② 현재 지속 상태 갱신
        ↓
③ 사건별 발생 조건 판정 → 특수 사건 후보 목록 생성
        ↓
    후보 없음 → special_events = []
    후보 있음 → 우선순위에 따라 사건 선택
        ↓
④ 사건 대상 Agent / 장소 결정
        ↓
⑤ 사건 효과 방향 생성
        ↓
⑥ 지속 상태 생성 또는 갱신
        ↓
⑦ special_events 반환
```

### 4.2 종료 조건

| 종료 | 처리 |
| --- | --- |
| 정상 종료 | 조건 판정 완료 → 사건 후보 생성 → 결과 반환 |
| 사건 없음 | `special_events = []`, tick 계속 진행 |
| 일반 이벤트 변환 LLM 실패 | 1회 재시도, 실패 시 원본 이벤트를 converted_events로 반환 |
| 특수 사건 서술 LLM 실패 | 1회 재시도, 실패 시 해당 special_event 생성 취소, tick 계속 진행 |

> 조건 판정 자체는 LLM이 아니라 시스템 로직이 담당하므로, 사건 발생 여부 판단을 LLM 호출 실패에 의존하지 않는다.

### 4.3 지속 상태 처리

#### 예시: 저주 전파

```
Tick 100: Agent A가 저주에 걸림 → world_state에 CURSED 기록
Tick 101: Agent A와 Agent B 접촉 → CURSE_SPREAD 후보 → Agent B도 CURSED
```

#### 예시: 실종

```
Tick 120: Agent A의 스트레스가 장기간 임계값 초과 → STUDENT_MISSING 발생 → Agent A = MISSING
Tick 121~125: Agent Runtime 실행 대상에서 제외
Tick 126: MISSING 상태 종료
```

지속 상태는 이벤트 설명에만 존재하면 안 된다. 반드시 `world_state` 또는 별도의 `world_effects`로 관리되어야 한다.

---

## 5. 도구

없음. Magic Layer는 다음 두 종류의 작업을 수행한다.
1. 일반 이벤트의 세계관 변환
2. 조건이 충족된 특수 사건의 서술 생성

특수 사건 발생 여부와 임계값 판정은 시스템 로직이 담당한다.

---

## 6. 컨텍스트 / 상태

Magic Layer 자체는 stateless로 유지할 수 있다. 이전 사건의 지속 효과는 `world_state`를 통해 전달받는다.

| 상태 | 저장 위치 | 수명 |
| --- | --- | --- |
| 저주 상태 | world_state / world_effects | 해제 조건까지 |
| 실종 상태 | world_state / agent_state | 설정된 기간 |
| 의식 실패 후 효과 | world_effects | 설정된 기간 |
| 사건 이력 | event history | 영구 기록 |

---

## 7. 다른 컴포넌트와의 관계

```
[Tick Orchestrator]
        ↓
[Event Master]
        ↓ regular_events
[Magic Layer]           ← 이 컴포넌트
        ↓
① 일반 이벤트 변환
② world_state 기반 사건 조건 판정
③ 특수 사건 생성
        ↓
[Policy Engine] → 실제 수치 효과 계산
        ↓
[Conflict Resolver] → [Commit] → [World State 갱신]
        ↓
다음 tick
```

---

## 8. 실패 모드

| 실패 시나리오 | 대응 |
| --- | --- |
| 변환 LLM 호출 실패 | 재시도 후 원본 이벤트 반환 |
| 특수 사건 서술 실패 | 사건 생성 취소 |
| 사건 조건 계산 오류 | 특수 사건 생성하지 않음 + 로그 |
| 여러 사건 조건 동시 충족 | 우선순위 적용 |
| 지속 상태 만료 처리 실패 | 다음 tick에서 상태 검증 및 로그 |
| 실종 Agent가 행동 목록에 포함 | Agent Runtime이 MISSING 상태 확인 후 제외 |
| LLM이 수치를 생성 | 출력 검증 단계에서 수치 제거 또는 거부 |
| 조건을 만족하지 않은 사건 생성 | 시스템 조건 검증 실패로 생성 거부 |

---

## 9. 시스템 프롬프트

```
당신은 Magic Academy 시뮬레이션의 Magic Layer입니다.

# 역할
시스템이 제공한 사건 후보와 대상 정보를 바탕으로
마법 세계관에 맞는 특수 사건의 설명을 생성합니다.

# 중요한 원칙
당신은 사건 발생 여부를 결정하지 않습니다.
사건 발생 여부는 시스템의 조건 판정 결과로 이미 결정되었습니다.
당신은 새로운 사건 타입을 임의로 만들지 않습니다.

# 생성 가능한 사건 타입
- MAGIC_EXPLOSION
- CURSE_SPREAD
- STUDENT_MISSING
- RITUAL_FAILURE
- MAGICAL_DISCOVERY

# 효과 규칙
구체적인 숫자를 생성하지 않습니다.

잘못된 예: "trust": -13
올바른 예: {"target": "trust", "direction": "decrease"}

실제 수치 변화는 Policy Engine이 계산합니다.

# 출력
반드시 JSON 형식으로만 응답합니다.
```

---

