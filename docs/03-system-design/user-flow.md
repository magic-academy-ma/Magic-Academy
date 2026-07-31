---
title: User Flow
source: confluence/05_TECH/user-flow.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/17367076/User+Flow
status: draft
visibility: public
updated: 2026-07-28
source_updated: 2026-07-27
---

```
메인 화면
│
├─ [시뮬레이션 시작]
│      │
│      ▼
│   시뮬레이션 시작 화면
│      │
│      ▼
│   User Persona 선택 화면
│      │
│      ├─ Persona 선택
│      │      │
│      │      ▼
│      │   User Persona 설정 화면
│      │      │
│      │      ├─ 성격 설정
│      │      └─ [설정 완료]
│      │             │
│      │             ▼
│      │        시뮬레이션 메인 화면
│      │             │
│      │             ├─ Agent 관찰
│      │             │      │
│      │             │      ▼
│      │             │   관계 그래프 확인
│      │             │      │
│      │             │      └─ [뒤로가기]
│      │             │             ↓
│      │             │        시뮬레이션 메인 화면
│      │             │
│      │             ├─ 시뮬레이션 저장
│      │             │      │
│      │             │      ▼
│      │             │   시뮬레이션 저장 화면
│      │             │      │
│      │             │      └─ [저장 완료]
│      │             │             ↓
│      │             │        시뮬레이션 메인 화면
│      │             │
│      │             └─ [시뮬레이션 종료]
│      │                    ↓
│      │               메인 화면
│      │
│      └─ [뒤로가기]
│             ↓
│        메인 화면
│
├─ [마이페이지]
      │
      ▼
   마이페이지 화면
      │
      ├─ 저장된 시뮬레이션 확인
      │      ↓
      │   시뮬레이션 불러오기
      │      ↓
      │   시뮬레이션 메인 화면
      │
      └─ [뒤로가기]
             ↓
        메인 화면
```
