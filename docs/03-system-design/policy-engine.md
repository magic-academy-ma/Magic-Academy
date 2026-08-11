---
title: Policy Engine 설계
source: confluence/05_TECH/policy-engine.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/14090319/Policy+Engine
status: draft
updated: 2026-07-28
source_updated: 2026-07-22
---

**기준 문서:** Agent Runtime 설계 (#11894790) · Tick Engine 스펙 (#12910622) · ERD 초안 (#12189697)

---

## 0. 한 줄 정의

Policy Engine은 Agent Runtime의 정성적 반응과 Event의 제안 효과를 버전 관리되는 결정론적 규칙에 적용하여, 검증 가능하고 범위가 제한된 상태·관계 변화 후보로 변환하는 계층이다.

Policy Engine은 LLM을 호출하지 않으며 DB도 직접 수정하지 않는다.

### 0.1 MVP 확정 범위

| 항목 | MVP 기준 |
| --- | --- |
| 처리 대상 | 생활 Agent 6명: Student 5명(User Persona 1명 포함) + Professor 1명 |
| 실행 시점 | Agent Runtime 병렬 실행 이후, Conflict Resolver 이전 |
| 계산 방식 | 단순 delta 가산 후 최종 clamp |
| 입력 반응 | valence, intensity, relationship_signals, state_signals |
| 관계 척도 | affection, closeness, trust, tension, rivalry, dependency |
| 상태값 | hunger, fatigue, stress, satisfaction, mood |
| Event | 일반 Event 기본 효과 + Magic Layer의 검증된 제안 효과 |
| 버전 | 모든 결과에 policy_version 기록 |
| 제외 | LLM 판단, Agent 행동 선택, 동시 행동 충돌 해결, DB commit |

---

## 1. 존재 이유

Policy Engine은 다음을 보장한다.
1. 동일한 입력과 동일한 policy_version이면 동일한 결과를 반환한다.
2. LLM은 의미만 제안하고 실제 수치는 코드와 규칙표가 결정한다.
3. 잘못된 target, 허용되지 않은 effect, 범위를 벗어난 delta는 commit 전에 차단한다.
4. 어떤 규칙 때문에 수치가 변했는지 effect 단위로 추적할 수 있다.
5. 규칙을 변경해도 policy_version으로 결과와 회귀 테스트를 재현할 수 있다.

---

## 2. 책임 경계

### 2.1 하는 일

- Runtime 결과의 schema, target, signal 유효성 재검증
- Action 자체의 기본 생리 효과 계산
- 정성적 signal과 intensity를 기본 delta로 변환
- **MBTI는 Runtime 판단에만 반영하고 Policy 단계에서 중복 수치 보정하지 않음**
- Event Policy Registry에서 Event 기본 효과 조회
- Magic Layer의 expected_effects를 허용 목록과 상한으로 검증
- 같은 Agent 결과 안에서 동일 원인의 중복 effect 제거
- 현재 상태를 기준으로 적용 후 값을 미리 계산하고 범위 clamp
- effect_id, rule_id, source, reason을 포함한 변경 후보 반환

### 2.2 하지 않는 일

- Student·Professor의 행동 선택
- 자연어 대사와 Memory 생성
- 동시성 충돌 해결 (→ Conflict Resolver)
- 양방향 대화 성립 여부와 상호 Intent 매칭
- 데이터베이스 저장 (→ Orchestrator Commit)
- WebSocket 브로드캐스트
- Event 생성 또는 마법화

---

## 3. 실행 위치와 순서

```
Event Master
  → Magic Layer
  → Agent Runtime × 활성 Agent 병렬 실행
  → Policy Engine     ← 이 컴포넌트
  → Conflict Resolver
  → Tick 단위 Commit
  → WebSocket Broadcast
```

Policy 계산 중 DB를 읽어 최신값을 다시 가져오지 않으며, Orchestrator가 전달한 snapshot만 사용한다.

---

## 4. 인터페이스 계약

### 4.1 입력: PolicyEvaluationInput

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| run_id | string | O | 시뮬레이션 실행 ID |
| tick_number | int | O | 현재 누적 tick |
| block | enum | O | MORNING, AFTERNOON, EVENING |
| policy_version | string | O | 적용할 정책 버전 |
| agent_snapshots | map[agent_id, AgentSnapshot] | O | 계산 전 상태·성격·위치 |
| relationship_snapshots | list[RelationshipSnapshot] | O | 계산 전 방향성 관계 |
| runtime_results | list[AgentRuntimeResult] | O | Agent별 Intent와 정성적 Reaction |
| events | list[FinalEvent] | O | Magic Layer 처리가 끝난 Event |
| schedules | list[ScheduleSummary] | O | 의무 일정 위반 판정용 |
| valid_agent_ids | set[id] | O | target 검증 |
| valid_location_ids | set[id] | O | location 검증 |

### 4.2 출력: PolicyEvaluationResult

> 출력 구조: `run_id`, `tick_number`, `policy_version`, `status`(EVALUATED / PARTIAL / REJECTED), `accepted_intents[]`(agent_id, action_type, target_agent_id), `effect_candidates[]`(effect_id, source_type, rule_id, target_type, source/target_agent_id, metric, delta, before, after_preview, reason), `rejected_effects[]`, `warnings[]`

Policy Engine의 출력은 아직 확정된 변경이 아니다. Conflict Resolver가 최종 합성한 뒤 Orchestrator가 commit한다.

---

## 5. 규칙 적용 순서

1. 필수 입력과 policy_version을 검증한다.
2. Runtime Intent의 action, target, location, event 참조를 검증한다.
3. Action 기본 효과를 생성한다.
4. Agent Reaction signal을 intensity별 기본 delta로 변환한다.
5. MBTI는 이미 Runtime의 행동·Reaction 판단에 반영되므로 Policy 단계에서 별도 수치 보정을 적용하지 않는다.
6. Event Registry의 기본 효과를 생성한다.
7. Magic Layer의 expected_effects를 검증해 허용된 후보만 생성한다.
8. 같은 source와 rule에서 나온 완전 동일한 effect를 제거한다.
9. Agent별·관계별 현재값을 기준으로 before와 after_preview를 계산한다.
10. 상태·관계 범위를 벗어나지 않도록 clamp한다.
11. effect_id 기준으로 정렬해 반환한다.

Conflict Resolver는 서로 다른 source에서 나온 후보를 합산하며, MVP에서는 단순 delta 가산을 사용한다.

---

## 6. Signal → delta 규칙

### 6.1 관계 signal

| intensity | 기본 절댓값 |
| --- | --- |
| LOW | 1 |
| MEDIUM | 3 |
| HIGH | 5 |

| signal | metric | 방향 |
| --- | --- | --- |
| TRUST_UP / DOWN | trust | + / - |
| AFFECTION_UP / DOWN | affection | + / - |
| CLOSENESS_UP / DOWN | closeness | + / - |
| TENSION_UP / DOWN | tension | + / - |
| RIVALRY_UP / DOWN | rivalry | + / - |
| DEPENDENCY_UP / DOWN | dependency | + / - |

관계 signal은 target_agent_id가 유효할 때만 적용한다. 자기 자신을 target으로 하는 관계 effect는 거부한다.

### 6.2 상태 signal

| intensity | 기본 절댓값 |
| --- | --- |
| LOW | 2 |
| MEDIUM | 5 |
| HIGH | 8 |

| signal | metric | 방향 |
| --- | --- | --- |
| HUNGER_UP / DOWN | hunger | + / - |
| FATIGUE_UP / DOWN | fatigue | + / - |
| STRESS_UP / DOWN | stress | + / - |
| SATISFACTION_UP / DOWN | satisfaction | + / - |
| MOOD_UP / DOWN | mood | + / - |

### 6.3 Reaction 적용 원칙

- valence는 설명과 검증에 사용하며 delta 방향을 직접 덮어쓰지 않는다.
- POSITIVE인데 STRESS_UP 같은 모순 조합은 허용하되 warning을 남긴다.
- 같은 Reaction 안에 동일 metric의 UP과 DOWN이 동시에 있으면 둘 다 거부하고 warning을 남긴다.
- Runtime이 숫자 delta를 임의로 포함해도 무시한다.

---

## 7. Action 기본 효과

Action 기본 효과는 행동 자체의 생리적 비용·회복만 표현한다.

| Action | 상태 기본 delta |
| --- | --- |
| ATTEND_CLASS | hunger +2, fatigue +3 |
| TEACH_CLASS | hunger +2, fatigue +4, stress +1 |
| STUDY | hunger +2, fatigue +4, stress +1 |
| TALK | fatigue +1 |
| EAT | hunger -20, satisfaction +2 |
| MOVE | hunger +1, fatigue +2 |
| REST | fatigue -15, stress -5 |
| PARTICIPATE_EVENT | hunger +2, fatigue +3 |
| HELP | fatigue +2, satisfaction +2 |
| AVOID | 기본 효과 없음 |
| WAIT | hunger +2, fatigue +1 |

- action target이나 location이 무효하면 해당 Intent는 WAIT fallback 후보로 바꾸고 원래 action 효과는 만들지 않는다.
- Action 기본 효과에는 성격 보정을 적용하지 않는다.

---

## 8. MBTI 처리 원칙

Student 5명의 초기 MBTI는 ISTJ, ESTP, INFP, ENTJ, ESFJ로 고정한다.

MBTI는 Agent Runtime이 행동 후보와 정성적 Reaction을 만들 때 사용한다. **Policy Engine은 같은 성격을 다시 delta에 더하지 않는다.**

이유:
1. Runtime의 signal과 intensity에 이미 성격의 영향이 반영된다.
2. Policy에서 MBTI별 추가 보정을 적용하면 같은 성격이 이중 반영된다.
3. MBTI는 범주형 대표 성향이므로 임의의 숫자 가중치를 두면 검증 근거가 약하다.
4. MVP는 단순 delta 가산과 재현성을 우선한다.

v0.2 정책의 실제 계산 입력: `signal + intensity + action_type + event_type + 현재 수치`

---

## 9. Event 정책

### 9.1 일반 Event 기본값

| Event Type | 참여 Agent 기본 delta | 비고 |
| --- | --- | --- |
| CLASS | stress +1 | Action 생리 효과와 별도 |
| GROUP_PROJECT | stress +3 | 관계 변화는 Reaction으로만 계산 |
| EXAM | stress +8, fatigue +5 | 성적·장학금은 MVP 이후 |
| MEETING | satisfaction +2 | 관계 변화는 Reaction으로만 계산 |
| MT | satisfaction +5, fatigue +5, hunger +3 | |
| FESTIVAL | satisfaction +6, fatigue +4, hunger +3 | |
| STUDENT_COUNCIL | stress +3, fatigue +3 | MVP 조직 범위에서는 Event만 허용 가능 |
| RANDOM_INCIDENT | Registry의 event_subtype 규칙 사용 | 자유 숫자 입력 금지 |

필수 CLASS 또는 EXAM을 정당한 충돌 일정 없이 AVOID한 경우: stress +5, satisfaction -3 추가.

### 9.2 Magic Layer expected_effects 검증

다음 조건을 모두 만족할 때만 후보로 채택한다.
- event_type과 event_subtype이 Event Policy Registry에 등록되어 있다.
- 대상 Agent가 참여자이거나 같은 장소의 관찰자로 명시되어 있다.
- metric이 MVP 허용 목록에 포함된다.
- **상태 delta 절댓값은 tick당 20 이하이다.**
- **관계 delta 절댓값은 tick당 12 이하이다.**
- 임시 비활성화는 등록된 event_subtype만 가능하며 최대 3 tick이다.
- 영구 삭제, 임의 SQL, 등록되지 않은 status 변경은 허용하지 않는다.

Registry 값과 expected_effects가 다르면 Registry를 우선하고 warning을 남긴다.

---

## 10. 중복 제거와 Conflict Resolver 경계

### 10.1 Policy Engine 내부 중복

다음 키가 모두 같으면 동일 effect로 간주한다.

```
source_type + source_id + rule_id + target + metric
```

동일 effect는 한 번만 남긴다.

### 10.2 Conflict Resolver가 처리할 것

- 서로 다른 Agent가 같은 Agent에게 만든 관계 변화 합성
- 상호 TALK가 실제 대화로 성립하는지 판정
- 동일 시간에 서로 다른 장소를 요구하는 행동
- Event 기본 효과와 Agent 반응이 의미상 같은 원인인지 최종 판정
- 최종 delta 합산과 commit 순서 확정

MVP 최종 계산:

```
final_value = clamp(current_value + sum(accepted_deltas), min, max)
```

---

---

## 12. 버전과 재현성

- 최초 버전: `policy-mvp-0.1`
- 규칙표의 숫자, 우선순위, 허용 Event 목록이 바뀌면 policy_version을 올린다.
- 문구나 주석만 바뀌면 버전을 올리지 않아도 된다.
- tick 결과에 prompt_version과 policy_version을 함께 저장한다.
- effect_id는 `run_id:tick:source:rule:target` 조합으로 생성한다.
- 동일 idempotency key를 다시 평가하면 같은 결과를 반환해야 한다.
- 정책 파일은 코드와 함께 Git으로 관리한다.

추천 모듈 구조:

```
app/simulation/policy/
├── engine.py
├── models.py
├── validators.py
├── registries/
│   ├── action_policy.py
│   ├── event_policy.py
│   └── signal_policy.py
└── versions/
    └── policy_mvp_0_1.py
```

---

## 13. 실패 처리

| 실패 | 처리 |
| --- | --- |
| 알 수 없는 policy_version | 전체 REJECTED, commit 금지 |
| 알 수 없는 signal | 해당 signal만 거부, PARTIAL |
| 잘못된 target | 해당 Intent를 WAIT 후보로 전환, effect 거부 |
| RuntimeResult schema 오류 | 해당 Agent 결과를 제외하고 warning |
| 등록되지 않은 Event subtype | expected_effects 거부, 안전한 일반 Event 규칙만 적용 |
| 범위 초과 effect | 허용 상한으로 자르지 않고 거부하여 설정 오류를 노출 |
| 중복 effect_id | 최초 1개만 유지 |
| 내부 예외 | tick commit 금지, 같은 snapshot으로 재시도 가능 |

---

## 14. 완료 기준

- 모든 MVP Action과 signal에 규칙이 존재한다.
- 일반 Event 8종의 기본 정책이 등록되어 있다.
- 알 수 없는 입력이 DB 변경으로 이어지지 않는다.
- 모든 effect에 policy_version, rule_id, source, reason이 기록된다.
- 같은 seed·snapshot·Runtime fixture로 같은 결과를 재현한다.
- 단위 테스트와 한 tick 통합 테스트가 통과한다.

---

