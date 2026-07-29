---
title: 04-feature-specs 개요
status: approved
visibility: public
updated: 2026-07-28
---

# 04-feature-specs/

기능별 상세 스펙 파일 모음. **구현 직전에 하나씩 추가한다.**

---

## 목적

AI가 특정 기능을 구현하기 전에 읽는 스펙 파일이다.  
도메인(`02-domain/`)과 시스템 설계(`03-system-design/`)를 기반으로, 해당 기능의 입출력·경계 조건·완료 기준을 구체화한다.

## 파일 추가 시점

- 기능 구현 직전에 작성한다.
- 아직 구현하지 않는 기능은 이 폴더에 미리 추가하지 않는다.

## 네이밍

```
FR-{번호두자리}-{기능명-kebab-case}.md
예) FR-01-student-agent.md
    FR-04-relationship.md
    FR-05-events.md
```

번호는 PRD 기능 요구사항(FR-XX) 번호를 따른다.

## 공개 범위

이 폴더는 **PUBLIC** 저장소에 포함된다.  
파일 작성 시 아래 내용은 포함하지 않는다.

- 팀원 실명·연락처
- 내부 KPI·비용·마진 수치
- 배포 시크릿·환경변수 값
