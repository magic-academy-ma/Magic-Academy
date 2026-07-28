# /context-scope

현재 작업 유형에 맞는 문서 로딩 범위를 안내한다.

## 입력

사용자에게 현재 작업 유형을 확인한다 (이미 제공됐으면 생략):
- 도메인 로직 구현 (새 기능)
- 버그 수정
- 문서 작업 / 이관
- PR 작성·리뷰
- 기타 (직접 설명)

## 실행

`docs/00-start-here/context-scope.md`를 읽고, 작업 유형에 맞는 로딩 범위를 안내한다.

## 출력 형식

```
## 컨텍스트 로딩 범위 — {작업 유형}

### Always Load (모든 작업 공통)
- docs/00-start-here/index.md
- docs/00-start-here/what-is-decided.md
- docs/00-start-here/what-is-pending.md
- docs/02-domain/ (7개 파일)
- docs/00-start-here/context-quality.md

### 이 작업에 추가로 필요한 파일
- {파일 경로} — {이유 한 줄}

### 이 작업에서 Skip할 파일
- docs/_meta/SYNC.md — 이관 운영 문서, 불필요
- (기타)

### 예상 총 토큰
~{숫자} 토큰
```

## 주의

- 로딩 범위는 `docs/00-start-here/context-scope.md`가 최신 기준이다.
- 해당 기능의 스펙 파일(`04-feature-specs/`)이 있으면 구현 직전에 추가로 로드한다.
- 페르소나별 자동 로딩 문서는 `AGENTS.md`의 역할별 페르소나 섹션을 참조한다.
