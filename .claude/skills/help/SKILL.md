---
description: 사용 가능한 Magic Academy Skills와 페르소나 목록을 출력할 때 사용
---

# /help

Magic Academy에서 사용 가능한 Claude Skills 목록을 출력한다.

## 출력

```
## Magic Academy Claude Skills

| 명령어 | 설명 | 주 사용자 |
|--------|------|-----------|
| /help | 이 목록 출력 | 전체 |
| /issue-writer | 작업 내용 받아 GitHub Issue 초안 생성 | @pm, 전체 |
| /pr-review | diff 분석 후 [Must]/[Question]/[Suggest]/[Nit]/[Good] 태그 기반 리뷰 | 전체 |
| /agent-spec | Agent 이름·역할 받아 페르소나·행동 규칙·LangGraph 노드 인터페이스 초안 생성 | @agent-dev, @system |
| /spec-draft | 기능 설명 받아 04-feature-specs/ 형식 스펙 초안 생성 | @pm, @system |
| /confluence-post | 문서 초안 받아 Confluence 페이지 생성 + Discord 공지 문구 출력 | @pm, @ai-native |
| /briefing | Done / In progress / Next 형식으로 세션 상태 정리 | 전체 |
| /context-scope | 현재 작업 유형에 맞는 문서 로딩 범위 안내 | 전체 |

## 페르소나

| 페르소나 | 담당자 | 주요 작업 |
|----------|--------|-----------|
| @system | 은혜 | Event Master, Tick Engine |
| @pm | 은혜 | Issue 작성, 스펙 초안 |
| @ai-native | 은혜 | AGENTS.md·Skills 관리 |
| @agent-dev | 가윤·지유 | Agent 설계, LangGraph |
| @magic-layer | 혜정 | Magic Layer, Frontend |
| @infra | 지유 | DB, Docker, CI/CD |
| @backend | 공통 | FastAPI, API |
| @fe | 공통 | React, React Flow |

세션 시작 시 본인 페르소나에 맞는 자동 로딩 문서는 AGENTS.md를 확인한다.
```
