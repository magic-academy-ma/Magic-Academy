---
title: MVP 범위 및 기능 우선순위
source:
  - confluence/02_PRODUCT_PLANNING/mvp-scope.md
  - confluence/02_PRODUCT_PLANNING/feature-priority.md
canonical:
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/17989637/MVP
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/17956886
status: draft
visibility: public
updated: 2026-08-06
source_updated: 2026-08-05
---

## MVP 포함

- 사용자 인증과 접근 제어
- Student Agent 5명과 Professor Agent 1명
- User Persona 초기 설정
- Tick 기반 자율 행동
- 일반 Event와 Magic 특수 사건
- Policy 기반 상태·관계 변화
- Inspector
- 관계 그래프
- 대표 캠페인
- 설정 저장·공유·가져오기
- Replay
- 시점 복원
- Magic OFF/ON 비교

## MVP 제외

- 25명 Agent 확장
- 동아리·기숙사 조직·총학생회
- 인간-동물 관계
- 대규모 사건
- 랜덤 날씨
- 상벌점
- 장학금
- 상세 학기·성적 운영
- 운영자용 writable Inspector
- 결제
- 공개 커뮤니티 피드 고도화
- 시점 분기

## MVP 완료 조건

- 대표 캠페인이 10 Tick을 정상 완료한다.
- 저장 결과의 Event·상태·관계 변화를 Replay할 수 있다.
- 기준 Tick의 상태·관계·Memory에서 시점을 복원할 수 있다.
- 인증된 사용자별 데이터 접근이 격리된다.
- Magic OFF와 ON 결과를 같은 기준으로 비교할 수 있다.
- Inspector에서 행동 이유를 확인할 수 있다.
- 범위 밖 상태·관계 Commit이 0건이다.

## 성과 지표

| 구분 | 지표 | MVP 목표 |
| --- | --- | --- |
| 실행 안정성 | 대표 캠페인 Tick 완료율 | 정상 실행의 100%가 Tick 10까지 완료 |
| Runtime | 유효 결과율 | 활성 Agent 실행의 95% 이상이 정상 Intent 또는 정의된 fallback 반환 |
| 데이터 안전 | Agent·Event·Policy의 DB 직접 쓰기 | 0건 |
| 참조 무결성 | 존재하지 않는 Agent·Location 참조 Commit | 0건 |
| 범위 정합성 | 상태·관계 범위 위반 Commit | 0건 |
| Inspector | Decision Explanation 제공률 | 정상 Intent의 95% 이상 |
| Magic | 특수 사건 오발생률 | 조건 미충족 상태에서 0건 |
| Replay | 원본 Tick 결과 재생 정합성 | 저장된 Event·상태·관계 변화와 100% 일치 |
| 복원 | 시점 복원 정합성 | 기준 Tick의 상태·관계·Memory를 누락 없이 복제 |
| 접근 제어 | 다른 사용자 비공개 Simulation 접근 | 0건 |
| 데모 | 대표 시나리오 완주 | 발표 제한 시간 내 1회 완주 |

## 단계별 확장

| 단계 | Student | Professor | 조직 |
| --- | --- | --- | --- |
| 1단계 MVP | 5명 | 1명 | 전공 |
| 2단계 | 10명 | 3명 | 전공 + 동아리 |
| 3단계 | 20명 | 5명 | 전공 + 동아리 + 기숙사 조직 + 총학생회 |

---

## 기능 우선순위

MVP 포함 여부와 구현 순서를 구분한다. P2 기능도 MVP 출시 전에는 완료하지만 핵심 실행 루프 이후에 구현한다.

| 우선순위 | 기능 묶음 | 관련 FR | 이유 |
| --- | --- | --- | --- |
| P0 | 인증·Simulation·Tick·Commit | FR-06, FR-19 | 나머지 기능의 기반 |
| P0 | Agent Runtime·상태·관계·Event·Policy | FR-01~05, FR-09, FR-20 | 핵심 시뮬레이션 루프 |
| P0 | 대표 캠페인·Inspector | FR-11, FR-18, FR-21 | 핵심 사용자 가치를 검증 |
| P1 | 설정 저장·Replay | FR-13, FR-16 | 결과를 다시 확인 |
| P1 | 시점 복원 | FR-17 | 비교 실험 제공 |
| P1 | Magic OFF/ON 비교 | FR-12, FR-20, FR-21 | 제품 차별점 강화 |
| P2 | 설정 공유·가져오기 | FR-14, FR-15 | 네트워크 효과 |
| P2 | 검색·필터·UI 고도화 | 관련 화면 기능 | 사용성 개선 |

### 의존성

- Replay는 Tick 이력과 Event·상태·관계 변경 기록이 선행되어야 한다.
- 시점 복원은 snapshot이 선행되어야 한다.
- 공유·가져오기는 인증과 소유권 정책이 선행되어야 한다.
- Magic ON/OFF 비교는 동일 seed와 변경 가능 시점 정책이 선행되어야 한다.
- Inspector는 Decision Explanation 저장·조회 계약이 선행되어야 한다.

### 결정 게이트 (미확정)

| 결정 | 영향 |
| --- | --- |
| Big Five와 MBTI의 Runtime 기준 | PRD·Runtime·API·ERD·Inspector |
| Magic ON/OFF 변경 시점 | PRD·API·Tick·Magic·캠페인 |
| 실행 1회 비용 예산 | KPI·모델·Memory |
| Replay snapshot 전략 | ERD·API·복원 |
