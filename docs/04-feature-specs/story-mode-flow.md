---
title: "FR-TBD 스토리모드 한 학기 진행 — 사람을 움직이는 마법"
status: draft
updated: 2026-10-19
---

# FR-TBD 스토리모드 한 학기 진행 — 사람을 움직이는 마법

## 1. 목적

스토리모드의 네 챕터(CHAPTER 1~4)를 **하나의 연속된 플레이**로 묶는다. 플레이어는 챕터를 골라서 하지 않는다. 프롤로그에서 임시 조정관으로 임명된 뒤 CHAPTER 1 → 2 → 3 → 4를 차례로 맡고, 마지막에 네 활동 기록으로 FINAL 엔딩을 본다.

## 2. 범위

**포함**
- 메인 화면의 스토리모드 진입점 1개(챕터별 버튼 없음)
- 프롤로그 → 챕터 도입 → 챕터 플레이 → 다음 챕터 → FINAL 순서 강제
- 챕터 결과(활동 기록) 수집과 FINAL 엔딩 판정
- CHAPTER 2·4의 저장·진행 API와 플레이 화면(지금까지는 판정 로직만 있었다)

**제외**
- 챕터별 세부 규칙. 각 챕터 문서를 따른다(`challenge-mode-rumor.md`, `challenge-mode-team-revival.md`, `challenge-mode-club-revival.md`, `challenge-mode-festival-booth.md`).

## 3. 진행 규칙

- 한 학기 = `story_runs` 한 행. `chapter`는 지금 맡은 챕터(1~4)이고, 5는 FINAL 단계다.
- 챕터는 서로 독립 run이다. 이전 챕터 결과가 다음 챕터의 상황이나 난이도를 바꾸지 않는다.
- 챕터 run은 "사건을 맡는다"를 누를 때 만든다. 같은 챕터에서 다시 눌러도 새 run을 만들지 않는다.
- 챕터 run이 끝나야 다음 챕터로 넘어갈 수 있다. 넘어갈 때 그 챕터의 `ChapterRecord`(등급·개별 엔딩·개입 기록)를 학기 기록에 남긴다.
- 진행 중에 나가도 다시 들어오면 마지막 위치에서 이어 한다.
- FINAL 이후 "새 학기 시작"을 누르면 새 `story_runs`가 시작된다.

## 4. FINAL 엔딩 판정 (2026-10-19 결정)

| 엔딩 | 판정 |
| --- | --- |
| `BEST` 「사람을 움직이는 마법」 | `GOOD` 기록이 4개 이상 |
| `BAD` 「해결하지 못한 것들」 | `BAD` 기록이 4개 이상 |
| `NORMAL` 「완벽하지 않은 해결사」 | 그 외 |

챕터가 4개이므로 BEST와 BAD는 네 챕터 모두 같은 등급일 때만 나온다.

## 5. 챕터별 활동 기록 등급

| 챕터 | GOOD | MIXED | BAD |
| --- | --- | --- | --- |
| 1 거짓 소문 | `RESOLVED` | `MISUNDERSTANDING` | `SPREAD` |
| 2 팀 갈등 | `UNITED` | `PARTIAL` | `DISBANDED` |
| 3 동아리 폐부 | `REVIVAL` | `CONDITIONAL` | `ONE_MEMBER`, `CLOSED` |
| 4 축제 부스 | `POPULAR` | `COMPLETED` | `HALTED` |

## 6. API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/v1/story` | 새 학기 시작 |
| GET | `/v1/story/current` | 가장 최근 학기(없으면 `null`) |
| POST | `/v1/story/{id}/chapter/start` | 지금 챕터의 run 생성(이미 있으면 그대로) |
| POST | `/v1/story/{id}/chapter/complete` | 끝난 챕터의 기록을 남기고 다음 챕터로 |
| GET·POST | `/v1/story/chapters/team-revival/{run_id}[/advance]` | CHAPTER 2 진행 |
| GET·POST | `/v1/story/chapters/festival-booth/{run_id}[/advance]` | CHAPTER 4 진행 |

CHAPTER 1·3은 기존 API(`/v1/challenges/rumor`, `/v1/challenges/club-revival`)를 그대로 쓴다.

## 7. CHAPTER 2·4 구현 메모

- 두 챕터 run은 `story_chapter_runs` 한 테이블에 두고, 챕터별 세부 상태는 `state` JSONB에 담는다.
- CHAPTER 2 초기 상태 프리셋 값(affection 낮음 / satisfaction 낮음 / stress 높음)은 방향만 확정이고 값은 임시값이다(`team_revival_chapter.INITIAL_PRESET`).
- CHAPTER 2 Tick 2·5·6·8처럼 개입 조치가 Event를 만들지 않는 Tick은 5명 `GROUP_PROJECT`(전술 연습)로 진행한다.
- 개입 선택에 걸린 시간은 직전 Tick이 저장된 시점부터 선택 제출까지로 잰다.
