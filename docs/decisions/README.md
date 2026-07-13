# ADR (Architecture Decision Records)

되돌리기 어려운 결정은 구현 전에 이 폴더에 기록한다.

**대상**: DB 선택, API 계약, 핵심 라이브러리, 인프라, Agent 통신 구조 등

## 파일명 규칙

```
NNN-kebab-case-title.md
예: 001-tech-stack.md
    002-agent-communication.md
    003-data-persistence.md
```

## 양식

```markdown
---
authored_with: Claude Code
features_used: []
date: YYYY-MM-DD
status: proposed | accepted | deprecated | superseded
---

# NNN. 결정 제목

## 배경

왜 이 결정이 필요한가.

## 결정

무엇을 선택했는가.

## 이유

왜 이 선택을 했는가. 대안과의 트레이드오프.

## 결과

이 결정이 가져오는 영향.
```

## 현재 미결정 항목 (결정 시 ADR 작성 필요)

- 기술 스택 (언어/프레임워크/LLM 제공자)
- Agent 간 통신 구조
- 데이터 저장 방식 (Agent 상태·관계 퍼시스턴스)
- Time Tick 최종 단위
