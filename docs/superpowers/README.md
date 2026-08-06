---
title: Superpowers — Magic Academy AI 협업 가이드
status: approved
visibility: public
updated: 2026-08-05
---

# Superpowers — Magic Academy AI 협업 가이드

> @ai-native 페르소나 세션 시작 시 이 파일을 로드한다.

Magic Academy에서 사용하는 Claude Code superpowers 스킬과 AI 협업 워크플로우를 정리한다.

---

## 스킬 라우팅 (Magic Academy 맥락)

| 상황 | 스킬 |
|------|------|
| 새 기능·시스템 설계 시작 | `superpowers:brainstorming` |
| 설계 확정 후 구현 계획 | `superpowers:writing-plans` |
| Issue·스펙 작성 | `issue-writer`, `spec-draft` |
| 구현 단계 | `superpowers:executing-plans` 또는 `superpowers:subagent-driven-development` |
| 버그·예상 외 동작 | `superpowers:systematic-debugging` |
| 구현 완료 후 검증 | `superpowers:verification-before-completion` |
| PR 리뷰 | `pr-review` |
| AI context 업데이트 | `docs/superpowers/ai-workflow.md` 참조 |
| Agent 설계 초안 | `agent-spec` |
| Confluence 페이지 생성 | `confluence-post` |
| 작업 상태 정리 | `briefing` |

---

## 문서 구조

```
docs/superpowers/
├── README.md          # 이 파일 — 스킬 라우팅 가이드
├── ai-workflow.md     # AI context 관리 운영 가이드
├── plans/             # 구현 계획 (writing-plans 출력물)
└── specs/             # 설계 스펙 (brainstorming 출력물)
```

---

## 관련 링크

- 컨텍스트 로딩 범위: `docs/00-start-here/context-scope.md`
- 팀 AI 사용 컨벤션: `docs/05-team-rules/ai-usage.md`
- AI context 설계 기록: `docs/_meta/ai-native-env-design.md`
