---
title: 8. AI 사용 컨벤션
source: confluence/09_CONVENTIONS/8.AI사용컨벤션
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/4521997/8.+AI
status: approved
visibility: public
updated: 2026-08-06
source_updated: 2026-07-31
---

# 8. AI 사용 컨벤션

## 8.1 목적

AI를 단순 코드 생성 도구가 아니라, 프로젝트 context를 기반으로 개발과 문서화를 돕는 협업 도구로 사용한다.  
단, AI가 생성한 결과물은 반드시 사람이 검토하고, 중요한 결정은 팀원이 직접 한다.

---

## 8.2 AI 사용 가능 작업

- 문서 초안 작성
- 회의록 정리
- Issue / PR 템플릿 작성
- 코드 구조 제안
- 리팩토링 방향 제안
- 테스트 케이스 아이디어 제안
- 에러 원인 분석 보조
- README / API 문서 정리
- Decision Log 초안 작성

---

## 8.3 AI 사용 주의 작업

- 핵심 아키텍처 결정
- 데이터 모델 확정
- 보안 관련 코드
- 배포 설정
- 인증 / 권한 관련 코드
- 팀의 최종 기획 결정

위 작업은 AI 제안을 참고할 수 있지만, 반드시 팀원이 직접 검토하고 결정한다.

---

## 8.4 AI에 넣으면 안 되는 정보

- API Key
- 비밀번호
- 개인 계정 정보
- 민감한 개인정보
- 공개하면 안 되는 외부 자료
- 팀원이 동의하지 않은 개인 정보

---

## 8.5 AI Context 문서 (docs/ 구조)

AI에게 제공하는 컨텍스트 문서는 GitHub `docs/` 폴더에서 관리한다.

```
docs/
├── 00-start-here/    # 진입점 (여기부터)
├── 01-product/       # 제품 정의 · MVP · 유저 시나리오
├── 02-domain/        # 핵심 도메인 모델 ← 구현 전 반드시 읽기
├── 03-system-design/ # 아키텍처 · 데이터 모델 · API
├── 04-feature-specs/ # 기능별 상세 스펙 (구현 직전 작성)
└── 05-team-rules/    # 코드 컨벤션 · Git · AI 협업 규칙
```

---

> **8.6 AI 사용 기록 양식 · 8.7 PR 표기 예시**는 사람이 직접 기록할 때 참조하는 양식이다.  
> AI 작업 중 로드할 필요 없음 — Confluence 원본 참조: https://jehye.atlassian.net/wiki/spaces/MA/pages/4521997/8.+AI
