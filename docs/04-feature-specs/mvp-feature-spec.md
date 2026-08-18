---
title: "[기능 명세서] 1단계 Magic Academy MVP"
source: confluence/03_REQUIREMENTS/mvp-feature-spec.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/16777778
status: draft
visibility: public
updated: 2026-08-06
source_updated: 2026-08-05
---

**기준 문서:** PRD · API 명세 및 공통 규약 (#12451842) · [Policy] MBTI → Big Five 초기값 및 허용 범위 (#21791106)

---

## 0. 개요 및 목적

이 문서는 Magic Academy 1단계 MVP의 화면별 기능·진입 경로·API 연결 및 오류 상태를 정의한다.

* **목적**: 기획·디자인·프론트엔드·백엔드가 동일한 사용자 흐름과 기능 계약을 구현하도록 기준을 제공한다.
* **범위**: Student Agent 5명(User Persona 1명 포함)과 Professor Agent 1명의 MVP 화면 및 기능을 다룬다.

## 1. 화면 목록

| 화면 ID | 화면명 | 진입 경로 | 관련 FR | 담당자 |
| --- | --- | --- | --- | --- |
| S0 | 로그인 화면 | 진입점 | — | @jiyou |
| S1 | 메인 화면 | S0 → [로그인 완료] | — | @jiyou |
| S2 | 시뮬레이션 시작 화면 (브랜딩) | S1 → [시뮬레이션 시작] | — | @Jehye, @박혜정 |
| S3 | User Persona 선택 화면 | S2 → [입학하기] | FR-03 | @김가윤 |
| S4 | User Persona 설정 화면 | S3 → [선택] | FR-03 | @김가윤 |
| S5 | 시뮬레이션 메인 화면 | S4 → [설정 완료] / S9 → [불러오기] | FR-01, FR-02, FR-03, FR-11 | @jiyou |
| S6 | Inspector 패널 | S5 Right Panel 하단 → [Inspector] 버튼 | FR-11 | @김가윤 |
| S7 | 관계 그래프 | S5 Right Panel → [관계 보기] | FR-04 | @김가윤 |
| S8 | 시뮬레이션 저장 화면 | S5 → [시뮬레이션 저장] | FR-13 | @jiyou |
| S9 | 마이페이지 | S1 → [마이페이지] | FR-13 | @박혜정 |

---

## 2. 화면별 기능 명세

### 2.0 로그인 화면 (S0)

**목적:** 사용자 인증 및 세션 확립. 로그인 성공 후 S1로 진입.

⚠️ 로그인 방식 미확정 — 이메일 / 소셜 로그인 중 방식 결정 필요. API 인증 헤더 방식도 API 명세서 §1.2 업데이트 후 반영.

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F0-01 | 로그인 | 이메일 또는 소셜 로그인 [방식 미확정] → 성공 시 세션 생성 → S1 이동 | [미확정] | ✅ | @jiyou |
| F0-02 | 회원가입 | 이메일 또는 소셜 계정으로 신규 가입 [방식 미확정] → 가입 완료 시 S1 이동 | [미확정] | ✅ | @jiyou |

**예외:** 로그인/가입 실패 시 에러 메시지 표시 후 현재 화면 유지

### 2.1 메인 화면 (S1)

**목적:** 시뮬레이션 시작 또는 마이페이지 진입

**진입:** S0 → [로그인 완료]

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F1-01 | 시뮬레이션 시작 진입 | [시뮬레이션 시작] 버튼 클릭 → S2 이동 | — | ✅ | @jiyou |
| F1-02 | 마이페이지 진입 | [마이페이지] 버튼 클릭 → S9 이동 | — | ✅ | @박혜정 |

### 2.2 시뮬레이션 시작 화면 — 브랜딩/전환 (S2)

**목적:** 시뮬레이션 시작 전 세계관 소개 및 분위기 전환. S1(메인) → S3(Agent 선택) 사이의 브랜딩 화면.

ℹ️ 콘텐츠 작성 주체 확정 — 세계관 소개 텍스트: @Jehye 작성 예정 / 배경 이미지: @박혜정 작성 예정. 기능적 설정 없음.

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F2-01 | 세계관 소개 표시 | Magic Academy 배경 텍스트 + 배경 이미지 | — | ✅ | @Jehye, @박혜정 |
| F2-02 | [입학하기] 버튼 | [입학하기] 클릭 → POST /simulations → simulation_id 발급 → S3 이동 | POST /simulations [미확정] | ✅ | @Jehye |
| F2-03 | 뒤로가기 | [뒤로가기] → S1 이동 | — | ✅ | @박혜정 |

### 2.3 User Persona 선택 화면 (S3)

**목적:** Student Agent 5명 중 User Persona로 플레이할 1명 선택

**관련 FR:** FR-03

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F3-01 | Agent 목록 조회 | 5명 목록(이름·전공·학년·agent_type) 표시 | GET /simulations/{simulation_id}/agents | ✅ | @김가윤 |
| F3-02 | User Persona 선택 | Agent 1명 선택 → [선택] 버튼 → S4 이동 | — | ✅ | @박혜정 |
| F3-03 | 뒤로가기 | [뒤로가기] → S1 이동 | — | ✅ | @박혜정 |

**예외:** API 오류(404/500) 시 에러 메시지 표시 후 현재 화면 유지

### 2.4 User Persona 설정 화면 (S4)

**목적:** 선택한 Agent의 성격 초기값 설정 후 시뮬레이션 시작

**관련 FR:** FR-03

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F4-01 | MBTI·성격 입력 | MBTI 5종 중 1개 선택 → 유형별 Big Five 기본값·허용 범위 적용 → `-50~+50` 축에서 허용 범위 안의 값을 5단위 슬라이더로 조절. MBTI 재선택 시 Big Five 전부 새 기본값으로 초기화 | GET /simulations/{simulation_id}/user-persona/config | ✅ | @박혜정, @김가윤 |
| F4-02 | 시뮬레이션 시작 | [설정 완료] → 선택한 기존 Student에 MBTI·Big Five 적용 → User Persona로 갱신 → 시뮬레이션 시작 → S5 이동. 설정 후 MBTI 중복 허용 | POST /simulations/{simulation_id}/user-persona → POST /simulations/{simulation_id}/start | ✅ | @Jehye |
| F4-03 | 뒤로가기 | [뒤로가기] → S3 이동, 선택 초기화 | — | ✅ | @박혜정 |

**예외:** 필수값 미입력 시 [설정 완료] 버튼 비활성화 / API 오류(409 이미 적용됨, 422 범위 초과) 시 에러 메시지 표시

### 2.4.1 시뮬레이션 파라미터 설정 화면 (S4.5)

**목적:** User Persona 설정 후, 시뮬레이션 시작 전에 실행의 초기 조건을 확정한다.

**진입:** S4 → [다음] → S4.5 → [시뮬레이션 시작] → S5

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F4-04 | 이벤트 파라미터 설정 | 이벤트 빈도·이벤트 영향도를 입력한다. 시작 전 기본값 설정과 시뮬레이션 진행 중 수정 모두 지원한다. | PUT /simulations/{simulation_id}/parameters | ✅ | @Jehye |
| F4-05 | Magic Layer 파라미터 설정 | Magic Layer 빈도·영향도를 입력한다. | PUT /simulations/{simulation_id}/parameters | ✅ | @박혜정 |
| F4-08 | 시뮬레이션 시작 | 파라미터가 저장된 Draft 시뮬레이션만 시작한다. 시작 후 이벤트 파라미터는 수정 가능하다. | POST /simulations/{simulation_id}/start | ✅ | @Jehye |

**오류 상태:** 범위 밖 값은 필드별 검증 오류로 표시한다. 이미 시작된 시뮬레이션의 설정 변경 요청은 "시작 후에는 변경할 수 없습니다."로 표시한다.

### 2.5 시뮬레이션 메인 화면 (S5)

**목적:** 시뮬레이션 실시간 관찰·조작의 핵심 화면. 3패널(좌·중·우) + Header + Event Log로 구성

**관련 FR:** FR-01, FR-02, FR-03, FR-11

| 기능 ID | 기능명 | 설명 | 위치 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- | --- |
| F5-01 | Tick 상태 표시 | 현재 Tick 번호·진행 시간 실시간 표시 | Header | GET /simulations/{simulation_id}/ticks/current | ✅ | @Jehye |
| F5-02 | 시뮬레이션 일시정지/재개 | [중지] / [재개] 버튼 토글 | Header | — | ✅ | @Jehye |
| F5-03 | 밤 시간 스킵 | [밤 스킵] 버튼 → 밤 블록 건너뛰고 다음 아침 블록으로 | Header | — | ✅ | @Jehye |
| F5-05 | Agent 목록 표시 | 6명 Agent 이름·현재 행동·위치 목록 | Left Panel | GET /simulations/{simulation_id}/agents | ✅ | @김가윤, @jiyou |
| F5-06 | Agent 검색 | 이름 검색 → 목록 필터링 | Left Panel | — | ✅ | @김가윤, @jiyou |
| F5-07 | Agent 필터 | 학생/교수/전체 필터 탭 (agent_type: STUDENT / PROFESSOR / USER_PERSONA) | Left Panel | — | ✅ | @김가윤, @jiyou |
| F5-08 | 학교 맵 Agent 위치 표시 | Agent 아이콘 + 현재 행동 말풍선 (공부중·식사·수업·휴식) | Center | GET /simulations/{simulation_id}/world/map | ✅ | @김가윤, @박혜정 |
| F5-09 | Agent 선택 → 상세정보 | Center 맵 또는 Left Panel 클릭 → Right Panel 해당 Agent 상세정보로 갱신 | Center / Left Panel | GET /agents/{agent_id} + GET /agents/{agent_id}/state | ✅ | @김가윤 |
| F5-10 | Agent 상태 게이지 표시 | 기분·배고픔·피로도·스트레스·만족도 게이지 바 | Right Panel | GET /agents/{agent_id}/state | ✅ | @김가윤 |
| F5-11 | Agent 소속 표시 | 전공·학년 (organizations 필드) | Right Panel | GET /agents/{agent_id} | ✅ | @김가윤 |
| F5-12 | 최근 Memory 표시 | 최근 5개 Memory 항목 | Right Panel | GET /agents/{agent_id}/memories?limit=5 | ✅ | @jiyou, @Jehye |
| F5-13 | 관계 그래프 진입 | [관계 보기] → S7 Modal 오픈 | Right Panel | — | ✅ | @김가윤, @박혜정 |
| F5-14 | Inspector 진입 | Agent 선택으로 Right Panel 요약 갱신 후, 하단 [Inspector] 버튼 클릭 → S6 Inspector 패널 오픈 | Right Panel 하단 | — | ✅ | @김가윤 |
| F5-15 | Event Log 실시간 표시 | WebSocket EVENT_CREATED 수신 → 신규 이벤트 자동 스크롤 추가 | 하단 | WS: EVENT_CREATED | ✅ | @Jehye, @박혜정 |
| F5-16 | Event Log → Agent 이동 | Event Log 항목 클릭 → 해당 Agent 선택 상태로 전환 | 하단 | — | ✅ | @Jehye, @박혜정 |
| F5-17 | WebSocket 실시간 갱신 | 연결: wss://{server}/v1/ws/simulations/{simulation_id}. API 명세서 §14 기준 수신 메시지 5종: TICK_UPDATED / AGENT_ACTION_UPDATED / EVENT_CREATED / RELATIONSHIP_UPDATED / SIMULATION_STATUS_UPDATED | 전체 | wss://{server}/v1/ws/simulations/{simulation_id} | ✅ | @Jehye |
| F5-18 | 시뮬레이션 저장 진입 | [저장] → S8 이동 | Header 또는 메뉴 | — | ✅ | @jiyou |
| F5-19 | 시뮬레이션 종료 | [종료] → S1 이동 | Header 또는 메뉴 | — | ✅ | @Jehye |

**예외:**

* WebSocket 연결 끊김 시 동작 [미확정]
* Tick 응답 지연 시 로딩 표시 여부 [미확정]

### 2.6 Inspector 패널 (S6)

**목적:** Agent의 판단 근거와 내부 상태를 시각화하는 상세 관찰 패널 (FR-11)

**관련 FR:** FR-11

**진입:** S5에서 Agent 선택 → Right Panel 하단 [Inspector] 버튼 클릭

**API:** GET /agents/{agent_id} (§5.2) + GET /agents/{agent_id}/state (§6.1) + GET /agents/{agent_id}/memories (§7.1) + GET /agents/{agent_id}/relationships (§8.1) 조합. F6-06은 `GET /agents/{agent_id}/decision-explanation?tick={tick}` API가 필요하나 현 API 명세 미반영이다.

참고: [Inspector 기능 정의 v0.6](https://jehye.atlassian.net/wiki/spaces/MA/pages/12582917)

| 기능 ID | 기능명 | 설명 | MVP | 담당자 |
| --- | --- | --- | --- | --- |
| F6-01 | Agent 기본 정보 표시 | 이름·전공·학년·현재 위치·현재 행동 (GET /agents/{agent_id}) | ✅ | @김가윤, @jiyou |
| F6-02 | 성격 표시 | MBTI 유형 + Big Five 5개 값을 Low / Neutral / High 라벨과 게이지로 표시하며 원본 값 범위는 -50~+50 | ✅ | @김가윤, @jiyou |
| F6-03 | 현재 상태 표시 | 기분·배고픔·피로도·스트레스·만족도 수치 (GET /agents/{agent_id}/state) | ✅ | @김가윤, @jiyou |
| F6-04 | 최근 Memory 표시 | 최근 행동·사건 기억 목록 (GET /agents/{agent_id}/memories) | ✅ | @김가윤, @jiyou |
| F6-05 | 관계 요약 표시 | 주요 관계 Agent와의 관계 수치 요약 (GET /agents/{agent_id}/relationships) | ✅ | @김가윤, @jiyou |
| F6-06 | 마지막 행동 판단 근거 표시 | Runtime이 구조화해 반환한 Decision Explanation(선택·대안·영향 요소) 표시. LLM 내부 추론은 노출하지 않음 | ✅ | @김가윤, @jiyou |
| F6-07 | 패널 닫기 | [닫기] → S5 복귀 | ✅ | @박혜정 |

**예외:** API 오류(404) 시 에러 메시지 표시 후 S5 복귀

### 2.7 관계 그래프 (S7)

**목적:** Agent 간 관계 구조를 그래프로 시각화 (Modal)

**관련 FR:** FR-03

**진입:** S5 Right Panel → [관계 보기] → Modal 오픈

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F7-01 | 관계 그래프 렌더링 | React Flow: Agent 노드 + 관계 엣지 표시 | GET /agents/{agent_id}/relationships | ✅ | @박혜정, @김가윤 |
| F7-02 | 관계 지표 표시 | 엣지 레이블: affection·closeness·trust·tension·rivalry·dependency | — | ✅ | @김가윤, @jiyou |
| F7-03 | 노드 클릭 → Agent 상세 | 노드 클릭 → S5 Right Panel 해당 Agent 상세정보로 이동 | — | ✅ | @김가윤, @jiyou |
| F7-04 | Modal 닫기 | [닫기] → S5 복귀 | — | ✅ | @박혜정 |

### 2.8 시뮬레이션 저장 화면 (S8)

**목적:** 현재 시뮬레이션 상태 저장

**관련 FR:** FR-13

**진입:** S5 → [저장]

ℹ️ **저장 API 추가 요청 중** — API 명세서에 댓글로 엔드포인트 추가 요청 완료. 혜정 확정 후 반영 예정. 제안: POST /simulations/{simulation_id}/save

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F8-01 | 저장 실행 | [저장] 버튼 → 시뮬레이션 상태 저장 | POST /simulations/{simulation_id}/save [미확정] | ✅ | @jiyou |
| F8-02 | 저장 완료 복귀 | 저장 성공 → S5 복귀 | — | ✅ | @jiyou |
| F8-03 | 저장 취소 | [취소] → S5 복귀, 저장 없음 | — | ✅ | @jiyou |

**예외:** 저장 실패 시 [미확정 — 혜정 확인 필요]

### 2.9 마이페이지 (S9)

**목적:** 로그인 사용자의 저장된 시뮬레이션 목록 조회 및 불러오기

**관련 FR:** FR-13

**진입:** S1 → [마이페이지]

ℹ️ **저장 목록·불러오기 API 추가 요청 중** — 저장본 불러오기는 시점 복원 조회와 별도 기능이다. API 명세 담당자 확정 후 엔드포인트를 반영한다.

| 기능 ID | 기능명 | 설명 | API | MVP | 담당자 |
| --- | --- | --- | --- | --- | --- |
| F9-01 | 저장된 시뮬레이션 목록 조회 | 로그인 사용자의 저장 목록(이름·저장일시) 표시 | GET /simulations [미확정] | ✅ | @jiyou |
| F9-02 | 시뮬레이션 불러오기 | [불러오기] → 저장된 Simulation 로드 → S5 이동. 특정 Tick 시점 복원 조회와 별도 기능 | API 확정 필요 | ✅ | @jiyou |
| F9-03 | 뒤로가기 | [뒤로가기] → S1 이동 | — | ✅ | @박혜정 |

**예외:** 불러오기 실패 시 [미확정 — 혜정 확인 필요]

---

## 변경 이력

| 버전 | 일자 | 변경 내용 |
| --- | --- | --- |
| 0.12.0 | 2026-08-05 | 저장된 Simulation 불러오기와 특정 Tick 시점 복원을 별도 기능으로 분리. F9-02에서 `/restore` 제안을 제거하고 불러오기 API는 담당자 확정 대상으로 남김. |
| 0.11.0 | 2026-08-04 | S4.5 Magic OFF 토글·OFF 확인 UI 제거. S4.5 목적에서 "Magic 사용 여부를 확정한다" 삭제. |
| 0.10.1 | 2026-08-03 | API 명세 §14를 기준으로 WebSocket 수신 이벤트를 5종으로 통일. Inspector 진입점을 Right Panel 하단 별도 버튼으로 확정. |
| 0.10.0 | 2026-07-31 | F4-01·F4-02·F6-02에 MBTI별 Big Five 기본값·허용 범위, -50~+50·5단위 슬라이더 반영. |
| 0.9.1 | 2026-07-30 | F4-01·F6-02 성격 입력·표시 방식을 MBTI 유형 선택 + Big Five 5개 토글(0~100)로 확정 반영. |
| 0.9.0 | 2026-07-29 | Magic ON/OFF 기능 제거 — F5-04 Magic ON/OFF 토글 삭제. |
| 0.8.0 | 2026-07-29 | S1·S2 테이블 API 컬럼 추가 / S2 F2-02에 POST /simulations 시뮬레이션 생성 API 명시. |
| 0.7.0 | 2026-07-29 | 문서 내부 정합화 — User Persona·관계 기능의 FR 참조, 관계 지표 용어, Inspector Decision Explanation 범위와 API 상태 정리. |
| 0.6.0 | 2026-07-28 | S2 콘텐츠 작성 주체 확정 — 세계관 소개 텍스트(@Jehye), 배경 이미지(@박혜정). |
| 0.5.0 | 2026-07-28 | S2 목적 확정 — 브랜딩/전환 화면 (세계관 소개 + [입학하기] 버튼). |
| 0.1.0 | 2026-07-28 | 최초 작성 — 화면 기준 기능 명세 초안. |
