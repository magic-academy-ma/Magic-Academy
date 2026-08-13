---
title: 도메인 개요
status: approved
updated: 2026-07-13
source: local/CLAUDE.md + 2차 회의록
---

# 도메인 개요

Magic Academy 시뮬레이션은 **3축(관계·조직·사건)**으로 구동된다.

```
관계 (Relationship)
  ↑ 영향
조직 (Organization) ──→ 사건 (Event) ──→ 관계 변화
  ↑                          ↑
배경 (Context): 시간·공간·날씨·학기  [방향을 만들지 않고 영향만 줌]
```

## 핵심 명제

> **관계는 Agent 간의 연결, 조직은 관계가 생기는 맥락, 사건은 관계와 조직을 변화시키는 트리거다.**

- **조직**이 Agent를 같은 공간에 묶으면 **관계**가 형성된다
- **사건**이 발생하면 기존 관계와 조직이 변화한다
- 배경은 이 세 축이 돌아가는 무대이며, 스스로 방향을 만들지 않는다

## 시뮬레이션 진행 방식

- 시간 단위: **Time Tick** — 1 Tick = 8분 = 1블록, 1일 = 3블록 (MORNING·AFTERNOON·EVENING)
- 입학 시점부터 Tick이 흐르며 사건이 발생하고 관계가 누적된다
- 사용자가 없어도 자율 진행, 개입 시 User Persona Agent를 통해 결과가 달라진다

## 각 도메인 파일

| 파일 | 내용 |
|------|------|
| `agents.md` | Agent 종류·역할·내부 상태 |
| `relationships.md` | 관계 척도·유형·변화 규칙 |
| `organizations.md` | 조직 목록·소속 규칙 |
| `events.md` | 사건 목록·트리거·효과 |
| `time-and-space.md` | Time Tick·공간·날씨 |

