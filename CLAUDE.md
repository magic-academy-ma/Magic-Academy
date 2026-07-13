# CLAUDE.md

Magic Academy — 마법 대학교를 배경으로 한 멀티 에이전트 LLM 시뮬레이션.  
agent들이 관계·조직·사건 속에서 상호작용하며 상태가 변화한다.

---

## 문서 구조

새 세션은 `docs/00-start-here/index.md`부터 읽는다.

```
docs/
├── 00-start-here/   # 진입점 (여기부터)
├── 01-product/      # 제품 정의 · MVP · 유저 시나리오
├── 02-domain/       # 핵심 도메인 모델 ← 구현 전 반드시 읽기
├── 03-system-design/# 아키텍처 · 데이터 모델 · API
├── 04-feature-specs/# 기능별 상세 스펙 (구현 직전 작성)
└── 05-team-rules/   # 코드 컨벤션 · Git · AI 협업 규칙
```

원본은 Confluence. `docs/`는 AI 개발용 스냅샷이며, 각 파일 frontmatter의 `canonical`이 원본 URL이다.

---

## 핵심 도메인 프레임

이 시뮬레이션은 3축으로 구동된다.

- **관계** — Agent 간 연결 (호감도·친밀도·신뢰도·긴장도·경쟁·의존도)
- **조직** — 관계가 생기는 맥락 (기숙사·동아리·전공·총학생회)
- **사건** — 관계와 조직을 변화시키는 트리거 (수업·시험·MT·축제…)

배경(시간·공간·날씨·학기)은 3축에 영향을 주지만 스스로 방향을 만들지 않는다.  
시간은 **Time Tick** 기반 — **24분 = 1일**, 밤 시간은 스킵 가능.

새 엔티티나 관계/사건 타입은 이 3축 프레임에 맞춰 정의한다.

---

## 작업 원칙

1. **미정 항목은 임의로 확정하지 않는다.** `docs/00-start-here/what-is-pending.md`를 확인하고, 미정 항목이 걸리면 사용자에게 확인한다.
2. **구현 전 `02-domain/`을 읽는다.** 도메인 모델과 어긋나는 구현은 하지 않는다.
3. **기능 구현 전 `04-feature-specs/`에 스펙이 있는지 확인한다.** 없으면 먼저 작성한다.
4. **컨벤션은 `05-team-rules/`를 따른다.**
5. **이 저장소는 Public이다.** 팀원 정보·시크릿·내부 KPI를 코드나 커밋에 포함하지 않는다.

---

## Claude 전용 힌트

- 새 기능·설계 시작 전 → `superpowers:brainstorming`
- 로직 구현·버그 수정 → `superpowers:test-driven-development`
- 완료 선언 전 → `superpowers:verification-before-completion`
- 독립 작업 병렬 실행 → `superpowers:dispatching-parallel-agents`
