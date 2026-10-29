---
title: "FR-TBD 도전과제 모드 3 — 동아리를 폐부에서 구하기"
status: draft
updated: 2026-10-19
---

# FR-TBD 도전과제 모드 3 — 동아리를 폐부에서 구하기

## 1. 목적

회원과 평판이 부족한 동아리를 3 Round 동안 운영해 최종 심사를 통과시킨다.
도전과제 공통 실행 모델은 `challenge-mode-team-revival.md` §4.1을 따른다.

## 2. 범위

**포함**
- 폐부 경고, 내부 갈등, 회원 모집, 최종 행사의 Event 계획
- 라운드별 사용자 개입 선택지
- 회원 수·평판·관계에 따른 네 가지 엔딩 판정
- 독립 Simulation과 도전과제 진행 상태 저장
- 도전과제 상태에서 아델·레오를 초기 회원으로, 리아·카이·세라를 가입 후보로 구분
- 9 Tick 실행 API와 도전과제 화면

**제외**
- 공용 OrganizationMembership 스키마의 실제 가입·탈퇴 persistence
- 업적 저장

## 3. 진행 구조

1 Round는 1 Day(3 Tick)이며, 나머지 Tick의 반응은 Agent Runtime이 자율 결정한다.

| Round | 핵심 상황 | 사용자 선택 |
| --- | --- | --- |
| R1 | 폐부 경고와 내부 갈등 | 중재하기 / 역할 재배정 / 지켜보기 |
| R2 | 신입 회원 모집과 홍보 | 공연 홍보 / 체험 행사 / 교수 추천 요청 |
| R3 | 성과 발표 또는 행사 | 성과 집중 / 관계 회복 / 안전 운영 |

### R1 — 폐부 경고와 내부 갈등

- T1: `RANDOM_INCIDENT / CLUB_CLOSURE_WARNING`을 전 부원에게 주입한다.
- 초기 부원은 아델(`student-01`)과 레오(`student-02`) 두 명이다.
- 리아·카이·세라는 R2 모집 전까지 폐부 대응 Event에 참여하지 않는다.
- T3: 사용자 선택을 `MEETING`, 분리된 `GROUP_PROJECT`, 추가 Event 없음 중 하나로 변환한다.

### R2 — 신입 회원 모집 및 홍보

- 공연 홍보는 `FESTIVAL`, 체험 행사는 `MEETING`으로 주입한다.
- 교수 추천 요청은 Professor를 포함한 `MEETING`으로 주입한다.
- 선택한 전략에 따라 도전과제 진행 상태의 회원 수와 평판을 갱신한다.
- 모집 Event에는 기존 회원과 가입 후보가 함께 참여하며, 결과에 따라 후보가 회원으로 전환된다.

### R3 — 성과 발표 또는 행사

- 성과 집중과 안전 운영은 `FESTIVAL`, 관계 회복은 `MEETING`으로 주입한다.
- 선택지는 Event의 맥락만 바꾸며 Agent의 최종 반응은 강제하지 않는다.

## 4. 엔딩 판정

초기 플레이테스트 기준은 이름 있는 상수로 분리한다.

- 최소 회원 수: `3`
- 평판 기준: `60`
- 관계 기준: 방향성 affection 평균 `>= 0`

| 엔딩 | 조건 |
| --- | --- |
| `REVIVAL` | 회원·평판·관계 기준 모두 충족 |
| `CONDITIONAL` | 최소 회원 수만 충족하고 나머지 기준 일부 미달 |
| `ONE_MEMBER` | 마지막 회원 1명 |
| `CLOSED` | 회원이 0명 또는 2명 이하 |

## 5. 업적 연결

- `다시 전성기다!`: `REVIVAL`
- `파국이다!`: 시작 시점보다 회원 관계가 악화
- `일단 사람부터 모아`: `CONDITIONAL`
- `나 홀로 동아리`: `ONE_MEMBER`

### 「파국이다!」 판정 기준 (2026-10-19 결정)

- run 시작 시점 회원 2명(`student-01`, `student-02`) 사이의 방향성 affection 2개를 기록한다(`club_challenge_runs.initial_member_affections`).
- run이 끝나면 **같은 두 회원 사이**의 affection을 다시 읽어, 평균이 시작 시점보다 낮으면 달성한다. 같으면 달성하지 않는다.
- 도중에 들어온 신입 회원과의 관계는 비교하지 않는다. 회원 구성이 바뀌어도 시작 회원끼리만 비교한다.
- 시작 시점 기록이 없는 run(이 기준 이전에 만든 run)은 판정하지 않는다.

### 지급

- 챕터 클리어(`CHAPTER3_CLEAR`)는 run이 중단(`ABORTED`) 없이 끝났을 때다.
- 스토리모드에서 "활동 기록 남기고 계속"을 눌러 챕터를 완료할 때, 위 업적과 클리어·「우유부단하시네요」를 계정에 지급한다(`achievements.md` §6).

## 6. 코드 구조

- 전용 순수 함수: `backend/app/simulation/challenge/club_revival.py`
- 실행·저장 서비스: `backend/app/services/club_challenge.py`
- API: `backend/app/api/club_challenge.py`
- 화면: `frontend/src/pages/ClubChallengePage.jsx`
- 폐부 경고 효과: 기존 MEDIUM stress 티어 재사용
- 공통 Event helper는 `forced_events.py`를 그대로 사용한다.

## 7. 완료 기준

- [x] 라운드별 선택지를 Event 계획으로 변환한다.
- [x] 네 가지 엔딩을 판정한다.
- [x] 폐부 경고 subtype을 Registry에 등록한다.
- [x] 관련 단위 테스트를 제공한다.
- [x] 독립 Simulation에서 9 Tick을 실행하고 진행 상태를 저장한다.
- [x] 시작·조회·진행 API와 사용자 선택 화면을 제공한다.
- [x] PostgreSQL 통합 테스트와 프론트 화면 테스트를 제공한다.

## 8. 남은 작업

- 실제 OrganizationMembership과 도전과제 전용 회원 상태의 연결
- [미정] 정식 FR 번호

## 9. 출처

- Notion `박지유 - 09.10 도전과제`
- Notion `게임 기획 방향 재정립 논의 결과`
- 2026-10-10 사용자 확정 선택지 및 엔딩 구조
