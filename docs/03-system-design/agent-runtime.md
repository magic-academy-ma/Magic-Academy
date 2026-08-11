---
title: Agent Runtime 설계
source: confluence/05_TECH/agent-runtime.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/11894790/Agent+Runtime
status: draft
visibility: public
updated: 2026-07-28
source_updated: 2026-07-22
---

**기준 문서:** 시스템 아키텍처 (#8290305) · Tick Engine 스펙 (#12910622) · Policy Engine 설계 (#14090319)

---

## 0. 한 줄 정의

Agent Runtime은 Tick Orchestrator가 전달한 현재 상태·관계·기억·마법화된 사건을 바탕으로 각 활성 Agent의 행동을 병렬 결정하고, DB를 직접 수정하지 않은 채 tick당 하나의 Intent와 Memory 후보를 반환한다.

### 0.1 MVP 확정 범위

| 항목 | MVP 확정 내용 |
| --- | --- |
| Student Agent | 총 5명 |
| 초기 MBTI 슬롯 | ISTJ, ESTP, INFP, ENTJ, ESFJ를 각각 1명씩 배정 |
| 일반 Student Agent | User Persona 지정 슬롯을 제외한 4명 |
| User Persona Agent | Student 5명 중 1명. 대표 캠페인 기본값은 INFP이며 일반 시뮬레이션의 지정 방식은 별도 확정 필요 |
| seed 생성 범위 | 이름, 학년, 성별, 초기 상태, 배경 Memory 등 세부 프로필 |
| Professor Agent | 전공 교수 1명 |
| 전체 Agent | 총 6명 |
| 전공 | 1개, Student 5명과 Professor 1명 모두 소속 |
| MVP 조직 | 전공만 포함 |
| MVP 제외 조직 | 동아리, 기숙사 조직, 총학생회 |
| User Persona 개입 | 시뮬레이션 시작 전 성격·성향 설정까지만 허용, 시작 후 직접 명령 불가 |
| Tick | 1일 3블록: 아침·오후·저녁, 현실 시간 8분당 1블록 |

### 0.2 전제조건

Agent Runtime이 실행되기 전에 다음 정보가 준비되어 있어야 한다.

| 전제조건 | 제공 주체 | 내용 |
| --- | --- | --- |
| TickContext | SimulationTickService | tick 번호, 날짜, 블록, 현재 학사 일정 |
| AgentSnapshot | AgentContextAssembler | Agent 프로필, 성격, 상태, 위치, 활성 상태 |
| RelationshipSnapshot | AgentContextAssembler | 현재 Agent와 다른 Agent 사이의 방향성 관계 |
| RetrievedMemory | MemorySearchService | 최신 Memory 2개와 RAG 검색 Memory 3개 |
| FinalEvent | Event Master → Magic Layer → Orchestrator | 마법 세계관 변환이 끝난 일반 사건과 마법 특수 사건 |
| ValidTargetSet | SimulationTickService | 이번 tick에 참조 가능한 Agent ID와 Location ID |

기본 동작:
- 이벤트가 없어도 활성 Student Agent는 상태·성격·기억을 바탕으로 자율 행동한다.
- Professor Agent는 자신이 참여해야 하는 수업·시험·사건이 있을 때만 실행한다.
- Memory나 Relationship이 없으면 빈 목록으로 처리한다.
- 필수 필드인 `tick`, `agent`, `state`가 없으면 LLM을 호출하지 않고 `WAIT` fallback을 반환한다.
- 비활성 Agent는 LLM을 호출하지 않고 `SKIPPED` 결과를 반환한다.

---

## 1. 존재 이유

### 1.1 해결하는 문제

Agent Runtime은 다음 문제를 해결한다.
- 동일한 사건에서도 Agent마다 다른 행동을 선택하게 한다.
- 사용자 설정이 User Persona의 행동에 지속적으로 반영되게 한다.
- 5명의 Student Agent가 사용자 입력 없이도 매 tick 자율적으로 행동하게 한다.
- Agent의 판단과 실제 DB 변경을 분리해 충돌과 중복 업데이트를 방지한다.
- Agent별 실행 실패가 전체 tick 실패로 전파되지 않게 한다.


---

## 2. 책임 경계

### 2.1 하는 일 (In Scope)

- 활성 Student Agent 5명의 tick별 행동 결정
- 관련 사건에 참여하는 Professor Agent의 행동 결정
- Agent 상태·성격·위치·관계·Memory·현재 사건 관찰
- 최신 2개 + RAG top-3 방식으로 최대 5개 Memory 선택
- Agent당 tick 하나의 대표 Intent 생성
- 행동의 대상 Agent, 이동 위치, 관련 Event 선택
- 수치가 아닌 정성적 반응 방향과 강도 생성
- OBSERVATION 또는 CONVERSATION Memory 후보 생성
- 큰 사건 참여자에 한해 REFLECTION 후보 생성
- JSON Schema 검증과 유효한 ID 검증
- 실패 시 `WAIT` fallback 반환
- 선택된 행동과 판단에 영향을 준 요소를 설명하는 구조화된 Decision Explanation 생성

### 2.2 하지 않는 일 (Out of Scope)

- 일반 대학 생활 사건 생성 → Event Master
- 일반 사건의 마법 세계관 변환과 마법 특수 사건 생성 → Magic Layer
- 학사 일정과 tick 시작·종료 관리 → SimulationTickService
- 관계·상태의 실제 숫자 delta 결정 → Policy Engine
- 여러 Intent의 충돌 해결 → Conflict Resolver
- Agent State, Relationship, Memory, Event의 DB 저장 → Commit 단계
- Memory embedding 생성과 pgvector 저장 → MemoryService
- Student의 고정 MBTI 슬롯 배정과 세부 프로필 seed 생성 → SimulationInitializer
- 동아리·기숙사·총학생회 행동 → MVP 제외
- 사용자의 시뮬레이션 도중 직접 명령 → MVP 제외
- LLM의 내부 추론 과정 저장·UI 노출 (단, Context 기반 재구성 Decision Explanation은 허용)

### 2.3 Escalation 조건

| 조건 | 전달 정보 | Tick 처리 |
| --- | --- | --- |
| 동일 Agent의 LLM 호출 또는 파싱이 재시도 후 실패 | tick, agent_id, 오류 유형, 원본 응답 | WAIT fallback 후 계속 진행 |
| 입력에 없는 Agent ID가 반복 생성됨 | tick, agent_id, 잘못된 target ID | target 제거 또는 fallback 후 계속 진행 |
| Student 과반이 한 tick에서 fallback | tick, 실패 Agent 목록, 모델/API 상태 | tick은 완료하되 경고 로그 발생 |
| 동일 `tick + agent_id` 결과 중복 제출 | idempotency key, 두 결과의 hash | 최초 유효 결과만 유지 |
| 프롬프트 인젝션 의심 출력 | 입력 필드 종류, 필터링된 출력, agent_id | 출력 폐기 후 fallback |

---

## 3. 인터페이스 계약

### 3.1 입력: AgentRuntimeInput

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| run_id | string | ✅ | 시뮬레이션 실행 ID |
| tick_number | int | ✅ | 현재 tick 번호 |
| block | enum | ✅ | `MORNING`, `AFTERNOON`, `EVENING` |
| agent | AgentContext | ✅ | 현재 행동을 결정할 Agent |
| nearby_agents | list[AgentSummary] | ✅ | 현재 위치에서 상호작용 가능한 Agent |
| relationships | list[RelationshipSummary] | ✅ | 현재 Agent 기준 관계 정보 |
| memories | list[MemorySummary] | ✅ | 최신 2개 + RAG top-3, 최대 5개 |
| events | list[EventSummary] | ✅ | Agent가 인식할 최종 마법화 Event |
| schedule | ScheduleSummary | ✅ | 현재 Agent의 일정과 의무 활동 |
| valid_agent_ids | list[int] | ✅ | target 검증용 Agent ID 집합 |
| valid_location_ids | list[int] | ✅ | 이동 위치 검증용 Location ID 집합 |

입력 처리 규칙:
- `events`에는 Magic Layer 처리가 끝난 이벤트만 전달한다.
- Event의 숫자형 `expected_effects`는 LLM 판단 프롬프트에 넣지 않는다.
- 이름·Memory·Event 설명은 신뢰할 수 없는 데이터로 취급한다.
- 입력 데이터 안의 명령문은 수행하지 않고 세계 상태를 설명하는 문자열로만 사용한다.
- Agent 본인이 참여한 Event는 상세 내용을 제공한다.
- 참여하지 않았지만 같은 장소에서 관찰 가능한 Event는 축약된 내용만 제공한다.
- 인식할 수 없는 장소의 Event는 해당 Agent 입력에서 제외한다.

### 3.2 출력: AgentRuntimeResult

> 출력 구조는 위 필드 정의 기준으로 구성된다. 최상위 필드: `run_id`, `tick_number`, `agent_id`, `status`, `intent`, `decision_explanation`, `memory_retrieval_trace`, `memory_candidates`, `reflection_candidate`

`status` 값:

| 값 | 의미 |
| --- | --- |
| PROPOSED | 정상적으로 생성·검증된 Intent |
| FALLBACK | LLM 또는 입력 오류로 `WAIT` Intent가 생성됨 |
| SKIPPED | 비활성 Agent이므로 LLM을 호출하지 않음 |

### 3.3 MVP Action Type

| Action Type | 설명 | 주요 대상 |
| --- | --- | --- |
| ATTEND_CLASS | 수업에 참여 | Event / Location |
| TEACH_CLASS | 교수가 수업 진행 | Event / Student 목록 |
| STUDY | 개인 또는 공동 학습 | Location / Agent |
| TALK | 다른 Agent와 대화 | Agent |
| EAT | 식당에서 식사 | Location |
| MOVE | 장소 이동 | Location |
| REST | 피로 회복을 위한 휴식 | Location |
| PARTICIPATE_EVENT | 시험·축제·특별 사건 등에 참여 | Event |
| HELP | 다른 Agent를 도움 | Agent / Event |
| AVOID | Agent 또는 Event를 피함 | Agent / Event |
| WAIT | 유효한 행동을 결정하지 못했거나 fallback | 없음 |

### 3.4 정성적 Reaction 계약

Agent Runtime은 관계·상태의 숫자 delta를 반환하지 않는다.

| 필드 | 허용 값 |
| --- | --- |
| valence | `POSITIVE`, `NEUTRAL`, `NEGATIVE` |
| intensity | `LOW`, `MEDIUM`, `HIGH` |
| relationship_signals | `TRUST_UP/DOWN`, `AFFECTION_UP/DOWN`, `CLOSENESS_UP/DOWN`, `TENSION_UP/DOWN`, `RIVALRY_UP/DOWN`, `DEPENDENCY_UP/DOWN` |
| state_signals | `HUNGER_UP/DOWN`, `FATIGUE_UP/DOWN`, `STRESS_UP/DOWN`, `SATISFACTION_UP/DOWN`, `MOOD_UP/DOWN` |

Policy Engine은 `signal + intensity + action_type + event_type + 현재 수치`를 버전 관리되는 규칙표에 적용해 실제 delta를 계산한다. MBTI는 Runtime의 행동·Reaction 판단에 반영하며, MVP Policy Engine에서 같은 성격을 다시 수치 보정하지 않는다.

### 3.5 부수 효과

| 동작 | 수행 여부 | DB 변경 |
| --- | --- | --- |
| 행동 결정 LLM 호출 | 활성 실행 Agent당 1회 | 없음 |
| Reflection LLM 호출 | 큰 사건 참여 Agent에만 조건부 1회 | 없음 |
| Memory 검색 | 입력 조립 단계에서 read-only | 없음 |
| Intent 저장 | Agent Runtime에서 하지 않음 | Orchestrator Commit 담당 |
| Memory embedding·저장 | Agent Runtime에서 하지 않음 | MemoryService·Commit 담당 |

---

## 4. 동작 설계

### 4.1 전체 실행 흐름

1. SimulationTickService가 tick과 학사 일정을 확정한다.
2. Event Master가 일반 사건을 만든다.
3. Magic Layer가 일반 사건을 마법화하고 필요 시 특수 사건을 추가한다.
4. Orchestrator가 활성 Agent와 조건부 Professor 실행 대상을 정한다.
5. AgentContextAssembler가 Agent별로 보이는 상태·관계·Memory·Event를 조립한다.
6. Student Agent 5명과 실행 조건을 만족한 Professor Agent를 병렬 실행한다.
7. 각 Agent Runtime은 Intent 하나와 Memory 후보를 반환한다.
8. Policy Engine이 정성적 signal을 숫자 delta로 변환한다.
9. Conflict Resolver가 상충하는 행동과 중복 효과를 조정한다.
10. Orchestrator가 tick 단위 트랜잭션으로 결과를 Commit한다.

### 4.2 Agent 내부 LangGraph (9노드)

| Node | 역할 | LLM 호출 |
| --- | --- | --- |
| ValidateInputNode | 필수 필드, 활성 상태, 유효 ID 검사 | 없음 |
| ObserveNode | 현재 위치에서 인식 가능한 Agent·Event·일정 구성 | 없음 |
| RetrieveMemoryNode | 최신 2개와 RAG top-3를 중복 없이 결합 | 없음 |
| EvaluateContextNode | 상태 임계 구간, 일정 의무, 관계 맥락을 구조화 | 없음 |
| DecideActionNode | 성격·상태·관계·기억을 종합해 대표 행동과 Decision Explanation 생성 | 1회 |
| GenerateIntentNode | 동일한 LLM 응답에서 Intent와 Decision Explanation을 구조화 | DecideAction과 동일 호출 |
| GenerateMemoryCandidateNode | 행동·대화에 대한 Memory 후보 구성 | DecideAction과 동일 호출 |
| ReflectIfNeededNode | 큰 사건이면 별도 Reflection 후보 생성 | 조건부 1회 |
| ValidateOutputNode | Schema, target, location, event 참조 검증 | 없음 |

> `SaveMemoryNode`는 `GenerateMemoryCandidateNode`로 변경. Agent Runtime은 Memory를 직접 저장하지 않는다.

### 4.3 Memory 검색·보존 규칙

Prompt에 포함하는 Memory는 최대 5개.

1. 가장 최근 Memory 2개를 먼저 고정한다.
2. 현재 Event·위치·상대 Agent를 검색 질의로 구성한다.
3. 나머지 Memory에서 점수를 계산한다.

```
memory_score = normalized_relevance + normalized_importance + normalized_recency
```

4. 최신 2개와 중복되지 않는 상위 3개를 선택한다.
5. Agent Runtime에는 최대 5개만 전달한다.

Agent당 저장 Memory는 최대 10개. 10개 초과 시:
- 최신 2개는 항상 보존한다.
- 큰 사건의 REFLECTION은 일반 OBSERVATION보다 우선 보존한다.
- 나머지 Memory 중 보존 점수가 가장 낮은 항목부터 제거한다.
- 제거와 embedding 갱신은 MemoryService가 담당한다.

초기 Memory:
- 일반 Student Agent 4명: seed 기반 배경 OBSERVATION 2개
- User Persona Agent: 사용자가 설정한 성격을 설명하는 초기 OBSERVATION 1개
- 초기 Memory의 `created_tick`은 0으로 기록한다.

### 4.4 행동 결정 규칙

#### Student Agent
- 활성 Student Agent 5명은 Event 참여 여부와 관계없이 매 tick 실행한다.
- 일정 의무, 현재 Event, 생리적 상태, 관계·Memory, MBTI 대표 성향을 함께 고려한다.
- 여러 Event에 참여해도 대표 Intent는 하나만 반환한다.
- User Persona Agent는 일반 Student와 같은 Runtime을 사용한다.
- User Persona의 차이는 시뮬레이션 시작 전 허용된 성격·성향 설정을 받는다는 점이다.
- 대표 캠페인에서는 INFP 슬롯을 사용하며, 일반 시뮬레이션의 슬롯 지정 방식은 별도 확정 필요.
- 시뮬레이션 시작 이후 User Persona에 대한 직접 명령은 받지 않는다.

#### Professor Agent
- 매 tick 호출하지 않는다.
- schedule상 교수 역할이 필요하거나 Event 참여자로 지정된 경우에만 실행한다.
- 호출되지 않은 tick에는 Intent와 Memory를 생성하지 않는다.

#### 복수 사건
- 모든 관련 Event를 관찰 컨텍스트로 제공한다.
- Agent는 성격·상태·의무 일정에 따라 하나의 행동을 고른다.
- 동일 Agent가 실제로 동시에 수행할 수 없는 복수 Intent를 만드는 것은 허용하지 않는다.

### 4.5 Event 효과와 Agent 반응의 중복 방지

Event Master와 Magic Layer의 `expected_effects`는 **제안값**이며 DB에 직접 반영하지 않는다. Agent Runtime의 LLM 입력에도 숫자형 예상 효과를 포함하지 않는다.

최종 효과 결정 순서:
1. Policy Engine이 `event_type`에 대응하는 기본 Event 효과를 조회한다.
2. `expected_effects`가 있다면 허용 범위와 참여 Agent를 검증한 참고값으로만 사용한다.
3. Agent Runtime의 정성적 Reaction을 규칙표를 통해 숫자 delta로 변환한다.
4. Conflict Resolver가 기본 Event 효과와 Agent 반응 효과를 합성한다.
5. 동일 원인의 효과가 두 번 들어오면 하나만 유지한다.
6. 최종 결과를 관계·상태 범위에 맞춰 clamp한다.


### 4.7 상태·성격 모델


#### MBTI 대표 성향 (고정 슬롯)

| MBTI | 대표 기질 | 핵심 성향 |
| --- | --- | --- |
| ISTJ | SJ 수호자 | 규칙, 안정, 책임 |
| ESTP | SP 장인 | 즉흥성, 행동, 현실 감각 |
| INFP | NF 이상주의자 | 가치관, 공감, 이상 |
| ENTJ | NT 합리주의자 | 논리, 전략, 목표 지향 |
| ESFJ | SF 공동체형 | 외향, 조화, 공동체 지향 |

- Student 5명은 위 MBTI를 각각 1명씩 사용한다.
- MBTI는 행동을 강제하는 규칙이 아니라 LLM이 후보 우선순위를 판단하는 대표 성향 컨텍스트다.
- 대표 캠페인에서는 INFP 슬롯을 User Persona로 지정한다.

### 4.8 비활성 Agent 처리

`STUDENT_MISSING` 등으로 Agent가 일시 비활성화되면 Commit 단계에서 다음 값을 저장한다.

```json
{
  "active_status": "INACTIVE_TEMPORARY",
  "inactive_until_tick": 45
}
```

- Orchestrator가 병렬 실행 목록을 만들 때 비활성 Agent를 제외한다.
- Agent Runtime도 입력 검증 단계에서 `active_status`를 확인한다.
- 비활성 Agent가 잘못 전달되면 LLM을 호출하지 않고 `SKIPPED`를 반환한다.
- `inactive_until_tick`이 지난 Agent의 재활성화는 SimulationTickService가 담당한다.

### 4.9 병렬 실행·재시도·종료

- Student 5명은 같은 world snapshot을 기준으로 병렬 실행한다.
- Professor는 실행 조건을 만족할 때 같은 병렬 batch에 포함한다.
- **Agent 간 실행 순서가 판단에 영향을 주지 않도록 실행 중 DB 변경을 금지한다.**
- 결과는 `agent_id` 기준으로 정렬해 Conflict Resolver에 전달한다.
- idempotency key는 `run_id:tick_number:agent_id` 형식.
- LLM 호출 또는 JSON 파싱 실패 시 같은 입력으로 1회 재시도한다.
- 재시도까지 실패하면 `WAIT` Intent와 `FALLBACK` 상태를 반환한다.
- 한 Agent의 실패는 다른 Agent 실행을 취소하지 않는다.

---

## 5. 도구 및 권한

| 도구 | 용도 | 권한 |
| --- | --- | --- |
| Haiku 4.5 | 행동·Intent·Memory 후보 생성 | 텍스트 입력 → 구조화 출력 |
| Haiku 4.5 조건부 호출 | 큰 사건 Reflection 생성 | 텍스트 입력 → 구조화 출력 |
| MemorySearchService | pgvector 기반 관련 Memory 검색 | read-only |

권한 원칙:
- LLM에는 DB, 파일 시스템, 네트워크 도구를 제공하지 않는다.
- Runtime 애플리케이션도 DB write 권한을 갖지 않는다.
- Intent·Memory·State·Relationship 쓰기는 Orchestrator Commit 경로로만 수행한다.

---

## 6. 컨텍스트와 상태

### 6.1 컨텍스트 초과 시 축약 전략

우선순위: `본인 상태 → 현재 일정 → 직접 참여 Event → 대상 Agent 관계 → Memory → 주변 정보`

축약 순서:
1. 직접 상호작용 대상이 아닌 Agent의 상세 관계를 제거한다.
2. RAG top-3 중 점수가 가장 낮은 Memory부터 제거한다.
3. 최신 Memory 2개는 유지하되 본문을 요약한다.
4. 관찰만 가능한 Event의 설명을 한 문장으로 줄인다.
5. 주변 Agent는 ID, 이름, 현재 행동만 남긴다.

제거 금지:
- 본인 ID, type, personality, state, location
- 현재 schedule
- 직접 참여 Event의 type과 participant ID
- valid ID 목록

MVP 목표: 행동 결정 호출당 입력 1,500 token 이하, 출력 500 token 이하.

### 6.2 유지되는 상태

Agent Runtime 자체는 stateless. 다음 호출에 필요한 정보는 모두 DB snapshot과 입력 컨텍스트로 다시 제공한다.

---

## 7. 다른 컴포넌트와의 관계

| 상대 | 방향 | 주고받는 것 |
| --- | --- | --- |
| SimulationTickService | 수신 | tick, block, schedule, 실행 Agent 목록 |
| Event Master | 간접 수신 (Orchestrator 경유) | 일반 Event |
| Magic Layer | 간접 수신 (Orchestrator 경유) | converted_events, special_events |
| AgentContextAssembler | 수신 | Agent별 상태·관계·Memory·관찰 범위 |
| Policy Engine | 송신 | 정성적 Reaction signal |
| Conflict Resolver | 송신 | 검증된 Intent와 후보 Memory |

Agent Runtime은 Event Master나 Magic Layer를 직접 호출하지 않는다.

---

## 8. 실패 모드

| # | 실패 시나리오 | 대응 | 심각도 |
| --- | --- | --- | --- |
| 1 | LLM API 호출 실패 | 1회 재시도 후 WAIT fallback | 중간 |
| 2 | JSON 파싱 또는 Schema 검증 실패 | 1회 재시도 후 fallback | 중간 |
| 3 | 존재하지 않는 target ID 생성 | target 제거 후 유효하지 않으면 fallback | 낮음 |
| 4 | 비활성 Agent가 실행됨 | LLM 호출 없이 SKIPPED | 중간 |
| 5 | Agent가 숫자 delta를 출력함 | 숫자 효과 필드 제거, signal만 사용 | 중간 |
| 6 | Event·Memory의 프롬프트 인젝션 | 출력 폐기, 재시도 후 fallback | 높음 |
| 7 | 같은 Agent 결과 중복 제출 | 최초 유효 결과만 유지 | 중간 |
| 8 | Memory가 10개를 초과함 | MemoryService 보존 규칙 적용 | 낮음 |
| 9 | 모든 Agent가 반복 행동 | Prompt·성격 반영 평가 후 회귀 케이스 추가 | 중간 |
| 10 | User Persona 설정이 행동에 미반영 | 성격 조건 테스트 실패 처리, Prompt 수정 | 높음 |
| 11 | Professor가 매 tick 불필요하게 호출됨 | Orchestrator 실행 조건 수정 | 낮음 |
| 12 | 한 Agent 실패가 batch 전체로 전파됨 | Agent 단위 예외 격리·fallback | 높음 |

---

## 9. 지표

| 지표 | MVP 목표 |
| --- | --- |
| Tick 완주율 | 100% |
| 유효 결과율 | 100% (fallback 포함) |
| Fallback 비율 | < 1% |
| 잘못된 참조 통과 건수 | 0건 |
| Memory 입력 개수 | 최대 5개 |
| 불필요한 Reflection 비율 | 0% |
| DB 직접 쓰기 | 0건 |
| 입력 token | < 1,500 |
| 출력 token | < 500 |
| 병렬 실행 지연 (P95) | < 5초 목표 |

---

## 10. 시스템 프롬프트

> 프롬프트 전문: `docs/03-system-design/agent-runtime-prompt.md`  
> 행동 결정용(§10.1) · Reflection용(§10.2) 두 종류. 프롬프트 수정 작업 시에만 로드.


## 11. 확정 사항

1. Student 5명에는 User Persona 1명이 포함된다.
2. 일반 Student 4명은 seed 기반으로 랜덤 생성한다.
3. 전공은 1개이며 Student 5명과 Professor 1명이 모두 소속된다.
4. Student 5명은 ISTJ·ESTP·INFP·ENTJ·ESFJ 슬롯을 각각 하나씩 사용한다.
5. 대표 캠페인의 User Persona는 INFP이며, 일반 시뮬레이션의 지정 방식은 Student Agent 설계에서 확정한다.
6. Student 5명은 매 tick 실행하고 Professor는 관련 Event가 있을 때만 실행한다.
7. Agent당 tick 하나의 Intent만 생성한다.
8. LLM은 정성적 행동·반응을 결정하고 숫자 delta는 Policy Engine이 계산한다.
9. 모든 관계 척도는 방향성 edge로 관리한다.
10. Runtime은 DB를 직접 수정하지 않고 Memory 후보만 반환한다.
11. 비활성 Agent 실행 제외는 Orchestrator가 소유하고 Runtime이 재검증한다.
12. 초기 관계와 일반 Student 프로필은 simulation seed로 재현 가능하게 생성한다.
13. 고백·배신·화해는 지속 관계 Label이 아니라 Event·Memory로 기록한다.

다른 설계 문서에서 확정이 필요한 사항: signal별 실제 delta (Policy Engine), 관계 Label 판정 임계값 (Relationship Policy), 학기 일정 (Tick Engine), 마법 특수 사건 기본 효과값 (Magic Layer / Policy Engine).

---
