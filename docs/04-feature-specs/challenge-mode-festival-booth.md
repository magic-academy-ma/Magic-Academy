---
title: "FR-TBD 스토리모드 CHAPTER 4 — 축제 부스 운영하기"
status: draft
updated: 2026-10-19
---

# FR-TBD 스토리모드 CHAPTER 4 — 축제 부스 운영하기

> 2026-10-15 개편: 9/24 기획 재정립에 맞춰 기존 "도전과제 2" 문서를 다시 썼다. 바뀐 점은 §10에 정리했다.

## 1. 목적

학기 말 아카데미 최대 행사인 **별빛제**에서 플레이어(임시 조정관)가 학생들과 함께 부스 하나를 운영한다. 교수는 이를 임시 조정관의 **마지막 실전 과제**라고 설명한다. 이 챕터는 남의 문제를 중재하지 않는다. 계속 바뀌는 운영 상황에서 누구에게 어떤 역할을 맡길지, 무엇을 먼저 해결할지, 누구를 쉬게 할지를 판단한다(핵심 테마: **협력과 판단**).

스토리모드 공통 실행 모델(독립 run, 1 Round = 1 Day(3 Tick), 컨트롤러 권한 3종 = Event 주입·정보 주입·일정 변경, 랜덤성 원칙, `WATCH` 선택지, 챕터 결과 기록 형식)은 `challenge-mode-team-revival.md` §4.1·§4.8을 그대로 따른다. 이 문서는 CHAPTER 4에서 **다른 점**만 정의한다.

## 2. 범위

**포함**
- Round 구성: R1 기획·준비, R2~R3 운영
- 라운드마다 1번씩, 총 3번의 개입 지점과 선택지
- 부스 담당 인원(booth staffing) 기록, 부스 성과 계산, 개별 엔딩 3종, 업적 판정

**제외**
- 동아리·총학생회 조직 모델. 이번 챕터에서는 5명이 별빛제 부스를 함께 맡은 학생이라는 서사 설정으로만 처리한다.
- 성과 step, 임계값, 공백 허용 횟수의 실제 수치. 이름 있는 상수로 분리하고 플레이테스트 후 조정한다.
- 엔딩 이후 UI/화면 구성

## 3. 입력 / 출력

| 항목 | 설명 |
| --- | --- |
| 입력 | 챕터 시작 요청(run 시드), R1 컨셉·역할 배정, R2 돌발 대응, R3 인력 조정 선택 |
| 출력 | Tick별 진행 상황, Tick별 부스 담당 인원, 개별 엔딩(`POPULAR` / `COMPLETED` / `HALTED`), 챕터 결과 기록, 업적 판정용 기록 |

## 4. 핵심 동작

### 4.1 등장 Agent와 플레이어

- Student 5명(A~E). 강제 초기 조건은 없고 기본 초기 상태에서 시작한다. run 시작 시점의 평균 satisfaction과 affection을 기록한다.
- **플레이어는 Agent가 아니다.** "플레이어가 학생들과 함께 운영한다"는 설정은 서사와 대사로만 표현하고, 실제 개입은 역할 배정과 지시(정보 주입·일정 변경)로만 한다. 부스 담당 인원에 플레이어는 포함되지 않는다.

### 4.2 부스 역할

R1에서 학생마다 역할 하나를 배정한다. 역할은 Agent 상태 필드가 아니다. **해당 Agent에게 주입하는 공지**("너는 오늘 ○○ 담당이다")와 **Event 참여자 조합**으로만 표현한다. 배정된 역할을 실제로 수행할지는 Agent가 정한다.

| 역할 | 설명 |
| --- | --- |
| `COUNTER` 부스 담당 | 부스를 지키며 손님을 응대한다. 부스 담당 인원 판정의 기준이다 |
| `PRODUCTION` 제작·진행 | 판매물이나 체험을 만들고 진행한다 |
| `SUPPLY` 조달 | 재료와 준비물을 관리하고 보충한다 |
| `PROMOTION` 홍보 | 부스 밖에서 손님을 모은다 |

### 4.3 Tick별 Event 구성

| Round / Tick | 내용 | Event 타입 | 참여자 |
| --- | --- | --- | --- |
| R1 T1 | 부스 기획 회의 | `MEETING` | 5명 |
| — | **개입 ①** 컨셉·역할 배정 (§4.4) | | |
| R1 T2 | 준비 작업(컨셉과 역할 반영) | `GROUP_PROJECT` | 5명 |
| R1 T3 | 리허설·사전 점검 | `GROUP_PROJECT` | 5명 |
| R2 T1 | 별빛제 개장 | `FESTIVAL` | 5명 |
| R2 T2 ★ | 돌발 상황 (§4.5) | `RANDOM_INCIDENT` | 5명 |
| — | **개입 ②** 돌발 대응 (§4.5) | | |
| R2 T3 | 운영 계속 | `FESTIVAL` (대응에 따라 변경) | 선택에 따름 |
| R3 T1 | 운영 둘째 날 | `FESTIVAL` | 5명 |
| R3 T2 ★ | 책임 공방 (§4.6) | `GROUP_PROJECT` (importance `high`) | 갈등 쌍 2명 |
| — | **개입 ③** 인력 조정 (§4.6) | | |
| R3 T3 | 운영 마무리 → 종료 평가 | `FESTIVAL` (조정에 따라 변경) | 선택에 따름 |

- 컨셉과 역할 배정은 R1 T2 이후 모든 Event의 title/description에 반영해 Agent가 맥락으로 알게 한다.
- 운영 Tick은 R2 T1~T3과 R3 T1~T3이다. 이 중 `FESTIVAL`로 진행된 Tick마다 부스 담당 인원을 기록한다(§4.7).

### 4.4 개입 ① 컨셉·역할 배정 (R1 T1 직후)

플레이어는 부스 컨셉 하나를 고르고, 5명에게 역할(§4.2)을 배정한다. 역할 배정을 생략하면 `WATCH`로 기록하고 학생들이 스스로 나눈다. 이때는 역할 공지를 주입하지 않는다.

컨셉은 수치를 바꾸지 않는다. 대신 **R2 T2에 나올 수 있는 돌발 상황의 후보 풀**을 바꾼다. 실제 돌발 상황은 후보 풀에서 run 시드 RNG로 하나를 뽑는다. 그래서 어떤 컨셉이 어떤 돌발로 이어질지 확정할 수 없다.

| 컨셉 | R2 T2 돌발 후보 풀 |
| --- | --- |
| `FOOD` 먹거리 부스 | `INGREDIENT_SHORTAGE`, `CUSTOMER_RUSH` |
| `EXPERIENCE` 체험형 부스 | `CUSTOMER_RUSH`, `RIVAL_BOOTH_ISSUE` |
| `EXHIBITION` 전시형 부스 | `RIVAL_BOOTH_ISSUE`, `INGREDIENT_SHORTAGE` |

역할 배정도 정답이 없다. 예를 들어 `SUPPLY`를 비우면 `INGREDIENT_SHORTAGE`에 약해지고, `COUNTER`를 1명만 두면 `CUSTOMER_RUSH`나 이탈에 약해진다. 하지만 어떤 돌발이 나올지는 미리 알 수 없다.

### 4.5 개입 ② 돌발 대응 (R2 T2 직후)

돌발 종류와 관계없이 공통 선택지를 주고, 조치는 R2 T3에 적용한다.

| 선택지 | R2 T3 조치 | 권한 | 트레이드오프 |
| --- | --- | --- | --- |
| `SEND_HELP` 문제 해결에 인원 투입 | 5명 `FESTIVAL`을 유지한다. 플레이어가 1명을 지목하면 그 학생에게 "부스를 잠시 떠나 문제를 처리해 달라"는 부탁을 주입하고 그 학생의 `FESTIVAL` 일정을 `is_mandatory = false`로 바꾼다. 지목하지 않으면 5명 모두에게 "누군가 문제를 처리해 달라"는 공지만 주입한다. **실제로 누가 부스를 떠날지는 Agent가 정한다** | 정보 주입 + 일정 변경 | 문제는 수습될 수 있다. 대신 부스 인원이 줄어 공백 위험이 커진다 |
| `KEEP_BOOTH` 부스 운영 집중 | 5명 `FESTIVAL`을 유지하고, "문제는 나중에 처리한다"는 공지를 주입한다 | 정보 주입 | 부스는 유지된다. 대신 문제가 방치되어 stress가 오르는 방향이다 |
| `EMERGENCY_MEETING` 긴급 대책 회의 | R2 T3을 5명 `MEETING`으로 바꾼다 | Event 주입 | 이 Tick은 성과 집계가 정체되고 부스는 공백이 된다. 대신 관계를 회복할 기회가 생긴다 |
| `WATCH` 지켜본다 | 조치 없음 | — | Agent 자율에 맡긴다 |

### 4.6 개입 ③ 인력 조정 (R3 T2 직후)

R3 T2 책임 공방의 갈등 쌍은 **R2 종료 시점 상태**로 정한다(기존 규칙 유지).

1. Student 5명의 10개 쌍마다 양방향 affection 합을 구한다.
2. 합이 가장 낮은 쌍을 갈등 쌍으로 고른다. 동률이면 run 시드 RNG로 고른다.
3. 고른 두 명만 참여하는 `GROUP_PROJECT`를 importance `high`로 주입한다(작은 실수를 두고 벌어지는 책임 공방).

공방 직후 플레이어가 개입하고, 조치는 R3 T3에 적용한다.

| 선택지 | R3 T3 조치 | 권한 |
| --- | --- | --- |
| `SUGGEST_REST` 휴식 권유 | stress+fatigue가 가장 높은 Agent에게 "조정관이 쉬어도 된다고 했다"는 공지를 주입하고, 그 Agent의 `FESTIVAL` 일정을 `is_mandatory = false`로 바꾼다. **실제로 쉴지는 Agent가 정한다** | 정보 주입 + 일정 변경 |
| `SWAP_ROLES` 역할 교체 | 갈등 쌍 두 사람의 역할을 맞바꾸는 공지를 주입한다. 두 사람의 역할이 같거나 개입 ①에서 역할 배정을 생략했다면, 갈등 쌍 중 1명(run 시드 RNG)을 `PROMOTION`(이미 `PROMOTION`이면 `COUNTER`)으로 옮기는 공지로 대신한다 | 정보 주입 |
| `MEDIATE` 중재 | 갈등 쌍에게 플레이어의 중재 대화 기억을 주입하고 두 사람 모두 `FESTIVAL`에 참여시킨다 | 정보 주입 |
| `WATCH` 지켜본다 | 조치 없음 | — |

- 기존 `ROTATE_REST`(강제 REST 오버라이드)는 `SUGGEST_REST`로 대체한다. 권유를 받은 Agent가 계속 일하기로 할 수도 있다. 반대로 권유를 받지 않은 Agent가 스스로 빠질 수도 있다.

### 4.7 부스 담당 인원 (booth staffing)

- 운영 Tick(R2 T1~T3, R3 T1~T3) 중 `FESTIVAL`로 진행된 Tick마다 `FESTIVAL` 참여자 가운데 행동이 `AVOID`가 아닌 인원을 부스 담당 인원으로 기록한다. Agent의 Tick 위치는 따지지 않는다(2026-10-15 결정).
- 그 Tick이 `MEETING`으로 바뀌었거나 부스 담당 인원이 0명이면 **부스 공백 Tick**으로 기록한다.
- 부스 공백 Tick 수는 엔딩과 업적 판정에 쓴다.

### 4.8 부스 성과 (booth_performance)

- 저장하지 않고 평가 시점에 Event 기록으로 계산한다. 기존 `calculate_project_progress()`를 재사용한다.
- 집계 대상은 R1 T2~T3 `GROUP_PROJECT`(준비)와 운영 Tick의 `FESTIVAL`에 실제 참여한 Agent의 `reaction.valence`다. POSITIVE면 ↑, NEGATIVE면 ↓, NEUTRAL이나 미참여면 정체다.
- 부스 공백 Tick은 성과 ↓ 방향으로 반영한다.
- R1 T1 `MEETING`, 긴급 대책 회의 `MEETING`, R3 T2 책임 공방은 집계하지 않는다.
- step은 CHAPTER 4 전용 이름 있는 상수로 분리한다.

### 4.9 신규 RANDOM_INCIDENT subtype

MEDIUM 티어(`policy-engine.md` §6, 기존 Registry 값)를 재사용하고 방향만 정의한다.

| subtype | 효과 방향 |
| --- | --- |
| `INGREDIENT_SHORTAGE` | stress ↑ |
| `CUSTOMER_RUSH` | fatigue ↑ |
| `RIVAL_BOOTH_ISSUE` | stress ↑ |

- 기존 `BUDGET_RUMOR`(R1 T2 소문)는 개편된 Tick 구성에서 쓰지 않으므로 Registry에서 제거한다.

### 4.10 개별 엔딩 (R3 T3 종료 시점)

| 엔딩 | 서사 | 판정 | 활동 기록 |
| --- | --- | --- | --- |
| `HALTED` | 갈등과 운영 문제가 겹쳐 부스가 사실상 중단된다 | 성과 미달, 또는 부스 공백 Tick 수가 허용치(`BOOTH_VACANCY_LIMIT`) 초과 | `BAD` |
| `POPULAR` | 끝까지 협력해 축제의 인기 부스로 마무리한다 | `HALTED`가 아니고, 번아웃 없음(전원 stress < 한계값), affection 평균 ≥ 임계값, 평균 satisfaction이 run 시작보다 상승 | `GOOD` |
| `COMPLETED` | 여러 문제가 있었지만 무사히 운영을 끝낸다 | 그 외 | `MIXED` |

- 번아웃은 기존과 달리 곧바로 `HALTED`가 되지 않는다. 대신 `POPULAR`를 막는다. 한 명이 무너져도 부스는 계속 돌아갈 수 있기 때문이다.

### 4.11 업적 판정

| 업적 | 상태 | 판정 |
| --- | --- | --- |
| CHAPTER 4 클리어 | 기획 확정 | run 정상 종료 |
| 쇼는 계속되어야 한다 | 기획 확정 | R2 T2 돌발과 R3 T2 공방이 모두 발생했는데도 부스 공백 Tick 0회이고 `POPULAR` 달성 |
| 여기 비었잖아 | 기획 확정 | 부스 공백 Tick 1회 이상 |
| 축제는 끝났다 | 기획 확정 | 종료 시점까지 stress 한계값 이상인 Agent가 1명 이상 나옴 |
| 쉼표도 운영이다 | 신규 제안 | `SUGGEST_REST`를 받은 Agent가 R3 T3에 실제로 쉬고, `POPULAR` 달성 |
| 적재적소 | 신규 제안 | 개입 ①에서 역할을 배정하고, 5명 모두 배정 역할대로 운영 Tick을 끝까지 수행 |
| 앙금은 축제 뒤에 | 신규 제안 | R3 T2 갈등 쌍의 양방향 affection이 종료 시점에 모두 0 이상 |

## 5. 경계 조건

- Tick Orchestrator·Event Master·Policy Engine 파이프라인 자체는 바꾸지 않는다.
- 5명 전원은 모든 Tick에서 Agent Runtime으로 자율 판단한다. 강제 REST는 없다.
- run이 중단되면 `ABORTED`로 처리하고 판정과 기록을 만들지 않는다.

## 6. 코드 구조

- 공통 부품을 재사용한다: `forced_events.py`, `round_driver.py`, `progress.py`. `llm_override.py`는 CHAPTER 2 문서 §6대로 입력 보강 래퍼로 바뀐 것을 쓴다.
- CHAPTER 4 전용 로직은 `backend/app/simulation/challenge/festival_booth.py`에 둔다. 다음을 바꾼다.
  - 컨셉 → 돌발 **후보 풀** 매핑과 시드 추첨(기존 1:1 확정 매핑 대체)
  - 역할 enum과 역할 공지 주입
  - Tick 계획: 9 Tick 재구성(§4.3), 개입 3곳
  - 선택지 enum: 개입 ② `SEND_HELP`/`KEEP_BOOTH`/`EMERGENCY_MEETING`/`WATCH`, 개입 ③ `SUGGEST_REST`/`SWAP_ROLES`/`MEDIATE`/`WATCH`
  - `ROTATE_REST`의 강제 REST 오버라이드 제거
  - 부스 공백 Tick 기록, 성과 집계 대상 변경, 엔딩 3종 판정
- 갈등 쌍 선정 로직은 그대로 재사용하고, 기준 시점만 R1 종료에서 R2 종료로 바꾼다.
- `round_driver.run_forced_event_round()`는 일정을 비필수로 바꿀 Agent(`non_mandatory_agent_ids`)를 받는다. Runtime 경로가 한 번 실행에 일정 1개만 쓰므로, 필수 그룹과 비필수 그룹을 따로 실행하고 결과를 합쳐 정책을 적용한다. 이 경우 두 그룹 사이의 TALK 충돌 해소는 일어나지 않는다.
- `RANDOM_INCIDENT_EFFECTS`에서 `BUDGET_RUMOR`를 제거한다.

## 7. 완료 기준

- [ ] 컨셉별 돌발 후보 풀 + 시드 추첨 단위 테스트
- [ ] 역할 배정 공지 주입, 개입 ① `WATCH` 시 공지 미주입
- [ ] 개입 ②·③ 선택지별 조치 단위 테스트(정보 주입·일정 변경만 사용하고 행동 지정 없음 확인)
- [ ] 갈등 쌍 선정 기준 시점 변경(R2 종료)
- [ ] 부스 공백 Tick 기록, booth_performance 집계 대상, 엔딩 3종 판정 단위 테스트
- [ ] `BUDGET_RUMOR` 제거, 강제 REST 경로 제거
- [ ] 업적 판정에 필요한 기록(공백 Tick, stress 최대값, 개입 선택과 소요 시간)

## 8. 남은 미정 항목

- (2026-10-15 결정) 부스 담당 인원은 `FESTIVAL` 참여 + `AVOID` 아님으로 판정한다(§4.7).
- (2026-10-15 결정) `SEND_HELP`는 플레이어가 1명을 지목하거나 지목 없이 넘길 수 있고, 실제로 누가 떠날지는 Agent가 정한다(§4.5).
- (2026-10-15 결정) `SWAP_ROLES`는 갈등 쌍 역할 맞교환을 기본으로 한다(§4.6).
- [미정] 엔딩 이후 UI/화면 구성, 정식 FR 번호

## 9. 관련 문서

- `docs/04-feature-specs/challenge-mode-team-revival.md` — 스토리모드 공통 실행 모델, CHAPTER 2
- `docs/02-domain/events.md`
- `docs/03-system-design/policy-engine.md`, `event-master.md`, `agent-runtime.md`

## 10. 개편 전후 비교

| 항목 | 개편 전(도전과제 2) | 개편 후(CHAPTER 4) |
| --- | --- | --- |
| 서사 | 동아리 부원 5명의 부스 | 임시 조정관이 학생들과 별빛제 부스 운영 |
| Round 구성 | R1 기획 / R2 준비 / R3 운영 | R1 기획·준비 / R2~R3 운영 |
| 개입 | 2회(R1 컨셉, R3 돌발 대응), R2 없음 | 3회(라운드마다 1회), 모두 `WATCH` 포함 |
| 역할 | 없음 | `COUNTER`/`PRODUCTION`/`SUPPLY`/`PROMOTION`(공지로만 표현) |
| 컨셉 → 돌발 | 1:1 확정 매핑 | 후보 풀 + 시드 추첨 |
| 휴식 | `ROTATE_REST` 강제 REST | `SUGGEST_REST` 권유 + 일정 비필수화 |
| 부스 공백 | 개념 없음 | Tick별 기록, 엔딩·업적에 사용 |
| 엔딩 | Perfect/Normal/Bad(번아웃이면 Bad) | `POPULAR`/`COMPLETED`/`HALTED`(번아웃은 `POPULAR`만 막음) + 활동 기록 등급 |
