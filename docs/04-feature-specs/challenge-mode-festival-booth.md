---
title: "FR-TBD 도전과제 모드 2 — 축제 부스 운영하기"
status: draft
updated: 2026-09-24
---

# FR-TBD 도전과제 모드 2 — 축제 부스 운영하기

## 1. 목적

도전과제 모드의 두 번째 시나리오. 동아리가 축제 부스를 기획·준비·운영하는 3일짜리 짧은 run을 사용자가 진행하며, 정해진 시점에 선택을 내린다.

도전과제 모드의 공통 정의(자유 시뮬레이션과 독립된 run, 컨트롤러의 개입 권한 2종, 1 Round = 1 Day(3 Tick))는 `challenge-mode-team-revival.md` §4.1을 그대로 따른다. 이 문서는 도전과제 1과 **다른 점**만 정의한다.

## 2. 범위

**포함**
- 9개 Tick 각각의 강제 Event 구성
- 사용자 개입 2회(R1 Tick 3 부스 컨셉, R3 Tick 2 돌발 대응)의 선택지와 강제 조치
- R2 Tick 2 갈등 대상 선정 규칙
- 신규 `RANDOM_INCIDENT` subtype 4종의 효과 방향
- 부스 성과(booth_performance) 계산 규칙, 엔딩 판정 규칙

**제외**
- 동아리·총학생회 조직 모델 도입(§4.1 — 조직 모델 없이 처리한다)
- 성과 step, 엔딩 임계값의 실제 수치 — 이름 있는 상수로 분리하고 플레이테스트 후 조정한다
- 엔딩 이후 UI/화면 구성

## 3. 입력 / 출력

| 항목 | 설명 |
| --- | --- |
| 입력 | 도전과제 시작 요청, R1 Tick 3 부스 컨셉 선택, R3 Tick 2 돌발 대응 선택 |
| 출력 | Tick별 진행 상황(강제 Event 결과), R3 Tick 3 종료 시점의 Perfect/Normal/Bad 판정 |

## 4. 핵심 동작

### 4.1 등장 Agent 및 초기 상태

- Student 5명(A~E)을 그대로 쓴다. **동아리 조직 모델은 도입하지 않고, "5명 = 같은 동아리 부원"이라는 서사 설정으로만 처리한다.** 스키마·조직 관련 코드 변경 없음.
- 강제 초기 조건은 두지 않는다. 기본 초기 상태에서 시작하고, 긴장은 R1 Tick 2 소문 Event로 만든다.

### 4.2 사용자 개입 지점

도전과제 1은 "Round 시작 시 선택 1회"였지만, 도전과제 2는 Round 중간 Tick에서 개입하며 R2에는 개입이 없다. 따라서 개입 지점은 `(round, tick)` 단위로 정의한다.

| 개입 지점 | 내용 |
| --- | --- |
| R1 Tick 3 실행 직전 | 부스 컨셉 선택 (§4.4) |
| R3 Tick 2 실행 직후 | 돌발 상황 대응 선택 (§4.6) |

### 4.3 Tick별 Event 구성

9개 Tick 모두 컨트롤러가 강제 Event를 주입한다. 스토리 뼈대 Tick(★)은 시나리오의 핵심 전환점이고, 나머지는 기존 Event 타입으로 흐름만 잇는다. 모든 Event의 이후 반응은 Agent 자율이다.

| Round / Tick | 내용 | Event 타입 | 참여자 |
| --- | --- | --- | --- |
| R1 T1 | 동아리 회의 | `MEETING` | 5명 |
| R1 T2 ★ | 예산·자원 부족 소문 | `RANDOM_INCIDENT` / `BUDGET_RUMOR` | 5명 |
| R1 T3 | 부스 컨셉 최종 결정 회의 (선택된 컨셉을 title/description에 반영) | `MEETING` | 5명 |
| R2 T1 | 재료 조달·디자인 작업 | `GROUP_PROJECT` | 5명 |
| R2 T2 ★ | 역할 배분 갈등 | `GROUP_PROJECT` (importance `high`) | 갈등 쌍 2명 (§4.5) |
| R2 T3 | 리허설·사전 점검 | `GROUP_PROJECT` | 5명 |
| R3 T1 | 개장 준비·홍보 | `FESTIVAL` | 5명 |
| R3 T2 ★ | 돌발 상황 (컨셉별, §4.4) | `RANDOM_INCIDENT` / 컨셉별 subtype | 5명 |
| R3 T3 | 운영 마무리 (대응 선택에 따라 변경, §4.6) → 종료 평가 | `FESTIVAL` 또는 `MEETING` | 선택에 따름 |

### 4.4 R1 Tick 3 — 부스 컨셉 선택

컨셉은 그 자체로 수치를 바꾸지 않는다. 컨트롤러 권한(Event 주입·Intent 오버라이드) 밖의 효과를 새로 만들지 않기 위해, **컨셉은 R3 Tick 2에 주입될 돌발 상황의 종류를 결정**하는 역할만 한다. 매핑은 확정적이다(랜덤 없음).

| 컨셉 | R3 T2 돌발 subtype |
| --- | --- |
| `FOOD` 먹거리 부스 | `INGREDIENT_SHORTAGE` (재료 소진) |
| `EXPERIENCE` 체험형 부스 | `CUSTOMER_RUSH` (손님 몰림) |
| `EXHIBITION` 전시형 부스 | `RIVAL_BOOTH_ISSUE` (경쟁 부스 이슈) |

선택된 컨셉은 R1 T3 `MEETING`과 이후 R2·R3 Event의 title/description에 반영해 Agent가 맥락으로 인지하게 한다.

### 4.5 R2 Tick 2 — 갈등 대상 선정

사용자 개입 없이 자율로 진행된다. 갈등 쌍은 **R1 종료 시점 상태**로 정한다.

1. Student 5명의 10개 쌍마다 양방향 호감도(affection) 합을 구한다.
2. 합이 가장 낮은 쌍을 갈등 쌍으로 선택한다.
3. 최저값이 동률이면 동률 쌍 중에서 **랜덤**으로 고른다. 재현성(replay)을 위해 run 단위 시드 RNG를 사용한다.

선정된 두 명만 참여하는 `GROUP_PROJECT`를 importance `high`로 주입한다(도전과제 1 Round 1 트리거와 같은 방식).

### 4.6 R3 Tick 2 — 돌발 대응 선택

돌발 종류와 관계없이 공통 선택지 3개를 제공하며, 강제 조치는 R3 Tick 3에 적용한다. 도전과제 1 Round 2와 같은 "성과 vs 사람" 트레이드오프 구조다.

| 선택지 | R3 T3 강제 조치 | 방향성 결과 |
| --- | --- | --- |
| `EMERGENCY_MEETING` 긴급 대책 회의 | T3를 `FESTIVAL` 대신 5명 `MEETING`으로 주입 | T3 성과 집계 없음(정체), 관계 회복 기회 |
| `ROTATE_REST` 교대 휴식 | stress+fatigue가 가장 높은 Agent 1명을 `REST`로 오버라이드하고 `FESTIVAL` 참여자에서 제외, 나머지 4명 `FESTIVAL` | 성과는 4명 기준 진행, 해당 Agent의 번아웃 방지 |
| `PUSH_THROUGH` 그대로 운영 | 오버라이드 없이 5명 `FESTIVAL` | 성과·상태 변화 모두 Agent 자율 반응에 따름 |

`ROTATE_REST`의 REST 응답은 도전과제 1의 강제 REST 응답을 재사용한다.

### 4.7 신규 RANDOM_INCIDENT subtype

도전과제 1과 같이 새 숫자를 만들지 않고 **MEDIUM 티어(`policy-engine.md` §6, 기존 Registry 값)를 재사용**한다. 방향만 정의한다.

| subtype | 효과 방향 |
| --- | --- |
| `BUDGET_RUMOR` | stress ↑ |
| `INGREDIENT_SHORTAGE` | stress ↑ |
| `CUSTOMER_RUSH` | fatigue ↑ |
| `RIVAL_BOOTH_ISSUE` | stress ↑ |

모두 `event_metadata.event_subtype`에 저장되므로 스키마 마이그레이션은 필요 없다(도전과제 1 §6과 동일).

### 4.8 부스 성과(booth_performance)

- 도전과제 1의 `project_progress`와 같은 방식이다. 저장하지 않고 평가 시점에 Event 기록에서 계산한다.
- 집계 대상: **R2의 `GROUP_PROJECT`(T1~T3) + R3의 `FESTIVAL`(T1, T3)**에 실제 참여한 Agent의 `reaction.valence`. POSITIVE ↑, NEGATIVE ↓, NEUTRAL·미참여 정체.
- R1 `MEETING`은 기획 단계이므로 집계하지 않는다.
- 기존 `calculate_project_progress()`를 재사용한다. 집계 건수가 도전과제 1보다 많으므로 step은 도전과제 2 전용 이름 있는 상수로 분리한다(값은 플레이테스트 후 조정).

### 4.9 엔딩 판정 (R3 Tick 3 종료 시점)

도전과제 1의 판정 구조를 유지하고, 스토리의 "성과 및 만족도 평가"에 맞춰 만족도 조건을 추가한다.

| 조건 | 기준 |
| --- | --- |
| 성과 | `booth_performance >= 임계값` |
| 번아웃 | Student 5명 전원 `stress < 한계값` |
| 관계 | 20개 방향성 affection edge 평균 `>= 임계값` |
| 만족도 | Student 5명 평균 `satisfaction`이 **run 시작 시점보다 상승** |

- **BAD**: 성과 미달 또는 번아웃 발생
- **PERFECT**: 성과·번아웃 조건을 만족하고 관계·만족도 모두 만족
- **NORMAL**: 그 외

성과/관계/스트레스 임계값은 도전과제 1의 상수를 초기값으로 재사용하되, 도전과제 2용 이름 있는 상수로 분리해 따로 조정할 수 있게 한다. 만족도 조건은 수치가 아닌 방향(시작 대비 상승)으로 판정한다. 이를 위해 run 시작 시점의 평균 satisfaction을 기록해야 한다.

## 5. 경계 조건

- 도전과제 1 §5와 동일하게 Tick Orchestrator·Event Master·Policy Engine 파이프라인 자체는 변경하지 않는다.
- 사용자 개입이 없는 R2, 그리고 R3 T3에서 오버라이드되지 않은 Agent는 항상 Agent Runtime으로 자율 판단한다.
- run이 중단되면 ABORTED로 처리하고 판정을 생성하지 않는다(도전과제 1 §5 제안값 채택).

## 6. 코드 구조

- 공통 부품은 그대로 재사용한다: `forced_events.py`, `round_driver.py`, `llm_override.py`, `progress.py`.
- 도전과제 2 전용 로직은 `backend/app/simulation/challenge/festival_booth.py`에 둔다(컨셉/대응 선택지 enum, Tick별 Event 계획, 갈등 쌍 선정, 엔딩 판정).
- 기존 `controller.py`(도전과제 1)는 이번 작업에서 이름·구조를 바꾸지 않는다.
- 신규 subtype 4종은 `policy/registries/event_policy.py`의 `RANDOM_INCIDENT_EFFECTS`에 추가한다.
- `forced_events.py`에는 `FESTIVAL` 강제 주입 헬퍼(`build_forced_festival`)를 추가한다.
- 알려진 제약: `round_driver.run_forced_event_round()`는 "강제 Event 1개, 참여자만 실행"까지 구현되어 있다. 9 Tick 전체를 연속 실행하는 통합은 도전과제 1과 마찬가지로 별도 작업이다.

## 7. 완료 기준

- [x] `festival_booth.py`: 컨셉·대응 enum, Tick별 강제 Event 계획, 컨셉 → 돌발 subtype 매핑
- [x] R2 T2 갈등 쌍 선정(최저 양방향 affection 합, 동률 시 시드 랜덤) 단위 테스트
- [x] R3 T3 선택지별 강제 조치(MEETING 대체 / REST 오버라이드+참여자 제외 / 무개입) 단위 테스트
- [x] 신규 subtype 4종 Registry 등록(MEDIUM 티어)
- [x] `build_forced_festival` 추가
- [x] booth_performance 집계 대상 필터링 + 엔딩 판정(만족도 방향 조건 포함) 단위 테스트

## 8. 남은 미정 항목

- [미정] 엔딩 이후 UI/화면 구성 (도전과제 1과 공통)
- [미정] 정식 FR 번호 (도전과제 1과 공통)

## 9. 관련 문서

- `docs/04-feature-specs/challenge-mode-team-revival.md` — 도전과제 모드 공통 정의, 도전과제 1
- `docs/02-domain/organizations.md`, `events.md`
- `docs/03-system-design/policy-engine.md`, `event-master.md`, `agent-runtime.md`
