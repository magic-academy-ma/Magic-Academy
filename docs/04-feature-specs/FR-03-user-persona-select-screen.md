---
title: "[페르소나 선택] FE 스펙"
status: draft
visibility: public
updated: 2026-08-25
---

# FR-03 페르소나 선택 화면 FE 스펙

> **상태**: Draft / **작성자**: @Jehye / **작성일**: 2026-08-25

## 0. 개요 및 목적

온보딩 2/3 단계. 사용자가 시뮬레이션에서 관찰할 Persona(Student Agent 5명 중 1명)를 선택한다.  
선택한 Persona는 페르소나 설정(Big Five) 화면으로 전달되며, 확정 후 변경 불가.

## 1. 컴포넌트 트리

```
PersonaSelectPage
├── BackLink (← 이전 / onboarding 또는 main으로 분기)
├── PageTitle
│   ├── StepIndicator ("PERSONA 선택 · 2 / 3")
│   ├── Title ("관찰할 Persona를 선택하세요")
│   └── Subtitle
├── CardRow
│   └── PersonaCard × 5
│       ├── Portrait
│       ├── SelectedBadge (선택됨 — 선택 시만 노출)
│       └── PersonaInfo
│           ├── Name, MBTI, Major
│           └── TraitTags
└── PageFooter
    ├── SelectedSummary (선택 후 노출)
    │   ├── SummaryPortrait
    │   ├── SummaryName
    │   └── SummaryMbti
    └── ConfirmButton ("이 Persona로 시작하기 →")
```

## 2. State / Props

| 이름 | 타입 | 출처 | 설명 |
|------|------|------|------|
| `selectedId` | `string \| null` | local state | 선택된 persona ID (초기값: `'leo'`) |
| `fromMain` | `boolean` | URLSearchParams(`from=main`) | 메인 진입 여부 (back 링크 분기) |
| `demoMode` | `boolean` | URLSearchParams(`mode=demo`) | 데모 모드 여부 |
| `personas` | `Persona[]` | static fixture | 5개 고정 페르소나 목록 |

## 3. API 연동

이 화면에서 API 호출 없음. 페르소나 목록은 정적 fixture 사용.  
선택 결과는 쿼리 파라미터(`?char={id}`)로 06-persona-setup에 전달.

| Method | Endpoint | 호출 시점 | 응답 |
|--------|----------|-----------|------|
| (없음) | — | — | — |

## 4. 빈 상태 / 로딩 / 에러 처리

| 상태 | 처리 |
|------|------|
| 초기 로드 | Leo 기본 선택 상태 |
| 확인 버튼 (선택 없을 때) | disabled |
| 로딩 / 에러 | 없음 (static data) |

## 5. Mock Data Fixture

```json
{
  "personas": [
    { "id": "adel", "name": "Adel", "mbti": "ISTJ", "major": "방어 마법",
      "traits": ["성실", "내향", "원칙주의"], "portrait": "/assets/character/Adel_ISTJ.png" },
    { "id": "leo",  "name": "Leo",  "mbti": "ESTP", "major": "마법 생물",
      "traits": ["충동적", "외향", "실용주의"], "portrait": "/assets/character/Leo_ESTP.png" },
    { "id": "ria",  "name": "Ria",  "mbti": "INFP", "major": "고대 마법",
      "traits": ["몽상적", "내향", "감수성"], "portrait": "/assets/character/Ria_INFP.png" },
    { "id": "kai",  "name": "Kai",  "mbti": "ENTJ", "major": "마법 도구 제작",
      "traits": ["리더십", "외향", "전략적"], "portrait": "/assets/character/Kai_ENTJ.png" },
    { "id": "sera", "name": "Sera", "mbti": "ESFJ", "major": "약초학 & 치유",
      "traits": ["사교적", "친화력", "조화"], "portrait": "/assets/character/Sera_ESFJ.png" }
  ]
}
```

## 6. 테스트 포인트

- **컴포넌트 단위 (vitest)**
  - 카드 클릭 시 `selected` 클래스 토글 및 SelectedBadge 노출
  - SelectedSummary: 선택 전 숨김, 선택 후 노출
  - ConfirmButton: 선택 없으면 disabled
- **E2E**
  - Leo 기본 선택 상태 확인
  - 카드 클릭 → footer 요약 갱신 확인
  - 확인 버튼 → `/persona-setup?char={id}` 이동 확인
  - `from=main` 파라미터 시 back 링크 분기 확인
- 카드 stagger 애니메이션 렌더링 확인
- 반응형: 1440px 기본, ≤1100px 2열 그리드, ≤520px 1열

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| 1.0.0 | 2026-08-25 | 최초 작성 | @Jehye |
