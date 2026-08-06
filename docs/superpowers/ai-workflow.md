---
title: Magic Academy AI 워크플로우 운영 가이드
status: approved
visibility: public
updated: 2026-08-05
---

# Magic Academy AI 워크플로우 운영 가이드

> @ai-native 페르소나 담당: 은혜

---

## 1. Confluence → docs/ 동기화

**원칙**: Confluence(원본) → docs/(AI 개발용 스냅샷). 원본은 Confluence.

**주기**: 주 2회 또는 Confluence 주요 변경 시

**절차**:
1. `docs/_meta/SYNC.md` 이관 큐에서 ⬜ 항목 확인
2. Atlassian MCP로 해당 Confluence 페이지 조회
3. docs/ 파일 생성 또는 업데이트 (frontmatter 포함)
4. SYNC.md 해당 항목 `⬜ → ✅`로 업데이트
5. PR을 통해 develop에 머지

**drift 감지**: ✅ 항목 중 Confluence 수정일이 `source_updated`보다 최신이면 drift 상태.
drift 항목은 SYNC.md에 `⬜ [파일명] — drift` 행으로 재등록한다.

---

## 2. AI context 파일 관리

| 파일 | 역할 | 수정 기준 |
|------|------|----------|
| `AGENTS.md` | 전체 팀 AI 진입점 | 프로젝트 규칙·페르소나 변경 시 |
| `docs/00-start-here/context-scope.md` | 작업별 로딩 범위 | 파일 추가·삭제 시, 토큰 수 변경 시 |
| `docs/00-start-here/context-quality.md` | AI 자가 점검 기준 | 품질 기준 변경 시 |
| `docs/05-team-rules/ai-usage.md` | AI 사용 컨벤션 | Confluence 원본 갱신 시 |
| `docs/_meta/SYNC.md` | 이관 큐 | Confluence 변경 감지 시 |

---

## 3. context-scope.md 토큰 예산 업데이트

파일 변경 후 토큰 예산을 재측정한다.

```bash
# 문자 수 측정 (chars ÷ 4 = 예상 토큰)
wc -m docs/00-start-here/*.md docs/02-domain/*.md docs/05-team-rules/*.md
```

측정 후 `context-scope.md`의 파일별 토큰 수치와 총합을 업데이트한다.

---

## 4. Claude 5 시대 context engineering 원칙

출처: https://yozm.wishket.com/magazine/detail/3875/

| 원칙 | 적용 방식 |
|------|----------|
| 규칙 최소화 | AGENTS.md에서 강한 제약 대신 판단 위임 |
| 반복 제거 | 동일 규칙은 한 파일에만, 다른 파일은 링크 |
| 점진적 공개 | context-scope.md로 작업별 필요 파일만 로드 |
| 예시 제한 | 구체적 예시 대신 규칙 한 줄로 표현 |
| 풍부한 참조 | 텍스트 설명보다 Confluence URL·파일 링크 |
