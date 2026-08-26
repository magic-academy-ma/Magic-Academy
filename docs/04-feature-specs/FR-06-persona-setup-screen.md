---
title: "[페르소나 설정] FE 스펙"
status: draft
visibility: public
updated: 2026-08-25
---

# FR-06 페르소나 설정 화면 FE 스펙

> **상태**: Draft / **작성자**: @Jehye / **작성일**: 2026-08-25

## 0. 개요 및 목적

온보딩 3/3 단계. 선택한 Persona의 MBTI와 Big Five 성격을 조정하고,
시뮬레이션 파라미터(일반 Event / Magic Layer)를 설정한 뒤 시뮬레이션을 시작한다.
설정 확정 후 Persona 성격과 Magic Layer 설정은 잠기며 변경 불가.

## 1. 컴포넌트 트리

```
PersonaSetupPage
├── PortraitPanel (좌측, 360px 고정)
│   ├── PortraitImage (선택된 캐릭터 이미지)
│   ├── GradientOverlay
│   └── PersonaInfo (하단)
│       ├── ChipRow (MBTI chip, major chip)
│       ├── CharacterName
│       ├── CharacterSub (MBTI · 전공 · 학년)
│       └── CharacterDesc
├── SetupFormPanel (우측)
│   ├── SetupNav
│   │   ├── BackLink (← / 02-persona-select)
│   │   ├── BrandLabel ("Persona 초기 설정 — {name}")
│   │   └── NavActions
│   │       ├── ShareImportButton (→ 15-share-import)
│   │       ├── JsonImportButton (모달 열기)
│   │       └── ExportButton (JSON 내보내기)
│   ├── SetupFormBody
│   │   ├── Section: 기본 정보 (읽기 전용)
│   │   │   └── FieldGrid (학년, 전공, 성별, 관심 분야)
│   │   ├── Section: MBTI 선택
│   │   │   ├── MbtiBtnGroup (5개 버튼)
│   │   │   └── MbtiHint ("재선택 시 Big Five 초기화")
│   │   ├── Section: Big Five 성격 조정
│   │   │   └── BigFiveSlider × 5
│   │   │       (개방성 / 성실성 / 외향성 / 우호성 / 정서 안정성, -50~+50)
│   │   └── Section: 시뮬레이션 파라미터 & Magic Layer
│   │       ├── EventParamCard (발생 빈도, 영향도)
│   │       ├── MagicLayerCard (발생 빈도, 영향도, ON/OFF 토글)
│   │       └── MagicOffWarning (토글 OFF 시 경고)
│   └── SetupFooter
│       ├── LockWarningText
│       ├── ChangePersonaButton (→ 02-persona-select)
│       └── StartSimulationButton (→ API 호출 후 03-simulation)
└── JsonImportModal (overlay)
    ├── TextArea (JSON 붙여넣기)
    ├── ImportError
    └── ApplyButton
```

## 2. State / Props

| 이름 | 타입 | 출처 | 설명 |
|------|------|------|------|
| `charId` | `string` | props | 선택된 persona ID (기본: `'leo'`) |
| `charInfo` | `CharData` | static fixture | 캐릭터 기본 정보 |
| `selectedMbti` | `string` | local state | 현재 선택된 MBTI (초기: charInfo.mbti) |
| `bigFive` | `BigFiveState` | local state | 5개 슬라이더 값 (-50~+50), MBTI 변경 시 초기화 |
| `eventParams` | `{freq, impact}` | local state | 일반 Event 파라미터 (10~100, 기본 50) |
| `magicParams` | `{freq, impact, enabled}` | local state | Magic Layer 파라미터 |
| `isImportModalOpen` | `boolean` | local state | JSON 가져오기 모달 표시 여부 |
| `importError` | `string \| null` | local state | JSON 파싱 오류 메시지 |
| `onBack` | `() => void` | props | 페르소나 선택으로 돌아가기 |
| `onStart` | `(charId, config) => void` | props | 시뮬레이션 시작 콜백 |

**MBTI → Big Five 기본값 매핑**

| MBTI | 개방성 | 성실성 | 외향성 | 우호성 | 정서안정성 |
|------|--------|--------|--------|--------|-----------|
| ISTJ | -20 | +35 | -25 | +10 | +25 |
| ESTP | +15 | -20 | +30 | -10 | +20 |
| INFP | +30 | -10 | -20 | +25 | -15 |
| ENTJ | +20 | +30 | +25 | -15 | +20 |
| ESFJ |  -5 | +20 | +20 | +35 | +15 |

## 3. API 연동

| Method | Endpoint | 호출 시점 | 응답 |
|--------|----------|-----------|------|
| `POST` | `/simulations/{simulation_id}/user-persona` | "시뮬레이션 시작" 버튼 클릭 | 201: `{id, agent_type, personality, status, locked}` |

**슬라이더 → API 변환**: `api_value = 50 + slider_value` (예: +15 → 65, -20 → 30)

**시뮬레이션 파라미터** (발생 빈도/영향도/Magic Layer): [미정] API 엔드포인트 미확인. 확정 전까지 로컬 상태로만 관리.

## 4. 빈 상태 / 로딩 / 에러 처리

| 상태 | 처리 |
|------|------|
| MBTI 재선택 | Big Five 슬라이더 값 MBTI 기본값으로 초기화 |
| API 호출 중 | "시뮬레이션 시작" 버튼 disabled + 로딩 텍스트 |
| 409 CONFLICT | "이미 Persona가 설정되었습니다" 에러 메시지 |
| 422 BUSINESS_RULE_VIOLATION | "설정값 범위 오류" 에러 메시지 |
| JSON 가져오기 파싱 실패 | ImportError 영역에 인라인 오류 표시 |
| Magic Layer OFF | 경고 배너 노출 |

## 5. Mock Data Fixture

```json
{
  "charData": {
    "adel": { "name": "Adel", "mbti": "ISTJ", "major": "마법 도서관학과",
              "interest": "규율", "grade": 3, "gender": "여",
              "portrait": "/assets/character/Adel_ISTJ.png",
              "desc": "원칙과 질서를 중시하는 수호계 마법학도." },
    "leo":  { "name": "Leo",  "mbti": "ESTP", "major": "마법공학과",
              "interest": "마법 생물", "grade": 2, "gender": "남",
              "portrait": "/assets/character/Leo_ESTP.png",
              "desc": "충동적이고 실용적인 Leo는 규칙보다 경험을 중시한다." },
    "ria":  { "name": "Ria",  "mbti": "INFP", "major": "고대 마법",
              "interest": "룬 문자", "grade": 1, "gender": "여",
              "portrait": "/assets/character/Ria_INFP.png",
              "desc": "직관과 감수성이 풍부한 몽상가." },
    "kai":  { "name": "Kai",  "mbti": "ENTJ", "major": "마법 도구 제작",
              "interest": "아티팩트", "grade": 4, "gender": "남",
              "portrait": "/assets/character/Kai_ENTJ.png",
              "desc": "냉철한 전략가이자 아티팩트 제작자." },
    "sera": { "name": "Sera", "mbti": "ESFJ", "major": "약초학 & 치유",
              "interest": "중재", "grade": 2, "gender": "여",
              "portrait": "/assets/character/Sera_ESFJ.png",
              "desc": "온화하고 친화력 있는 치유 마법사." }
  },
  "presetExportExample": {
    "version": 1,
    "mbti": "ESTP",
    "bigfive": { "openness": 15, "conscientiousness": -20,
                 "extraversion": 30, "agreeableness": -10, "stability": 20 },
    "params": { "event": { "freq": 50, "impact": 50 },
                "magic": { "freq": 60, "impact": 70, "enabled": true } }
  }
}
```

## 6. 테스트 포인트

- **컴포넌트 단위 (vitest)**
  - MBTI 버튼 클릭 → Big Five 슬라이더 값 초기화 확인
  - 슬라이더 조작 → 옆 수치 레이블 실시간 갱신 (+/- 부호 포함)
  - Magic Layer OFF 토글 → 경고 배너 노출
  - JSON 가져오기: 유효 JSON → 슬라이더 값 반영, 무효 JSON → 에러 메시지
  - 내보내기: 현재 상태가 올바른 JSON으로 직렬화되는지 확인
- **E2E**
  - `charId=adel` 진입 → PortraitPanel이 Adel 이미지·정보로 렌더링
  - "시뮬레이션 시작" → `POST /user-persona` 호출 후 다음 화면 이동
- 슬라이더 값 범위 경계값 확인 (-50, 0, +50)
- 반응형: 1440px 기준 (좌우 분리 레이아웃)

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| 1.0.0 | 2026-08-25 | 최초 작성 | @Jehye |
