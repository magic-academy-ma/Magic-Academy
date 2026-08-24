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
| /pr-writer | 브랜치 diff와 커밋 내역 분석 후 PR 템플릿 초안 생성 및 Draft PR 등록 | 전체 |
| /pr-review | diff 분석 후 [Must]/[Question]/[Suggest]/[Nit]/[Good] 태그 기반 리뷰 | 전체 |
| /spec-draft | 기능 설명 또는 Figma URL을 받아 스펙 초안 생성 (모드 A/B) | 전체 |
| /slice-plan | Slice 구현 전 작업 분할 및 파일 변경 계획 수립 | @dev, 전체 |
| /logic-review | 도메인/아키텍처 문서와 정합성 검토 | @dev, 전체 |
| /confluence-post | 문서 초안 받아 Confluence 페이지 생성 | @pm, 전체 |
| /briefing | Done / In progress / Next 형식으로 세션 상태 정리 | 전체 |
| /context-scope | 현재 작업 유형에 맞는 문서 로딩 범위 안내 | 전체 |

## 페르소나 (3종 활동 기반)

| 페르소나 | 주요 작업 |
|----------|-----------|
| @pm | 기획·스펙 — Issue 작성, 스펙 초안, 범위 관리 |
| @dev | Slice 구현 — 백엔드·DB·인프라 (팀 전체 공통) |
| @fe | 프론트엔드 — React, React Flow, 화면 컴포넌트 |

세션 시작 시 페르소나별 자동 로딩 문서는 AGENTS.md를 확인한다.
```
