---
title: 인프라 — 배포 환경 및 운영 전략
source: confluence/05_TECH/infra.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/6750218/Docker+Compose
status: approved
visibility: public
updated: 2026-07-21
source_updated: 2026-07-13
---

> 이 문서는 다음 Confluence 선행조사 페이지 3개를 통합한 문서다.
>
> * [Docker Compose 서비스 분리](https://jehye.atlassian.net/wiki/spaces/MA/pages/6750218/Docker+Compose) (2026-07-13)
> * [Cloud PaaS 비교: Render / Railway / Fly.io](https://jehye.atlassian.net/wiki/spaces/MA/pages/7733270/Cloud+PaaS+Render+Railway+Fly.io+pgvector) (2026-07-13)
> * [Secret / 환경변수 관리 전략](https://jehye.atlassian.net/wiki/spaces/MA/pages/7733282/Secret) (2026-07-13)
> * [모니터링 / 로깅 전략](https://jehye.atlassian.net/wiki/spaces/MA/pages/7929917) (2026-07-13)
>
> 확정 결론 요약은 [기술 스택 확정](./tech-stack.md) 인프라 섹션도 참고한다.

---

## 1. 환경 구성 개요

| 기간 | 환경 | 구성 |
| --- | --- | --- |
| Week 1–2 | 로컬 | Docker Compose — pgvector / FastAPI+uvicorn / React+Vite 서비스 분리, `magic-net` 브리지 네트워크 |
| Week 3+ | Railway | 단일 서버 + Railway PostgreSQL(pgvector) |
| Week 5–6 (조건부) | Redis 추가 | 실제 부하 문제 발생 시에만 도입 |

---

## 2. 로컬 개발 환경 — Docker Compose

### 2.1 결론

**B안 (서비스 분리 + 공통 네트워크)** 채택. 각 서비스를 독립 컨테이너로 분리하되 `magic-net` 브리지 네트워크로 연결한다. Week 1-2 로컬 개발에 최적화하며, Week 3+에서 Cloud PaaS로 전환 시에도 각 서비스를 독립적으로 배포 가능하다.


### 2.3 docker-compose.yml (Week 1-2)

```yaml
version: "3.9"

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: magic_academy
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - magic-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d magic_academy"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/magic_academy
    depends_on:
      db:
        condition: service_healthy
    networks:
      - magic-net

  frontend:
    build: ./frontend
    command: npm run dev -- --host
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000
      VITE_WS_URL: ws://localhost:8000
    networks:
      - magic-net

networks:
  magic-net:
    driver: bridge

volumes:
  pgdata:
```

**pgvector 이미지 선택 이유**

* `pgvector/pgvector:pg16` — PostgreSQL 16 + pgvector 공식 이미지. 별도 extension 설치 불필요
* 초기화 SQL은 `./backend/init.sql` 또는 Alembic 마이그레이션으로 처리

### 2.4 개발 워크플로우

```shell
# 전체 실행
docker compose up -d

# 백엔드만 재시작
docker compose restart backend

# DB 초기화 (데이터 삭제)
docker compose down -v && docker compose up -d
```

### 2.5 리스크

| 구분 | 내용 |
| --- | --- |
| pgvector 버전 호환 | pgvector/pgvector:pg16 이미지 사용 시 extension 버전 고정됨. 업그레이드 시 이미지 태그 변경 |
| 핫리로드 | frontend에서 `node_modules` 볼륨 마운트 제외 필수. 누락 시 컨테이너 내부 모듈 덮어씀 |
| M1/M2 Mac | `platform: linux/amd64` 명시 또는 `linux/arm64` 호환 이미지 확인 필요 |
| Week 3+ 전환 | Cloud PaaS 이전 시 db만 managed DB로 교체. backend/frontend는 컨테이너 이미지 그대로 활용 가능 |

---

## 3. Cloud PaaS — Railway

### 3.1 결론

Magic Academy MVP에서는 **Railway + PostgreSQL(pgvector)** 조합을 사용한다.

이유:
* PostgreSQL 지원
* Docker 없이 빠른 배포 가능
* GitHub 연동이 간단
* 초기 비용이 낮음


### 3.3 배포 방식

* FastAPI + PostgreSQL(pgvector) + Railway 조합
* GitHub Push 시 Railway가 자동 배포하도록 설정

### 3.4 리스크

* Railway 무료 사용량 초과 가능
* AI 토큰 비용 증가
* PostgreSQL 용량 증가

---

## 4. 환경변수 / Secret 관리

### 4.1 결론

GitHub Secrets + Railway Environment Variables 사용

### 4.2 환경별 관리 방식

| 환경 | 방식 |
| --- | --- |
| 로컬 | `.env`, `.env.example` |
| CI | GitHub Secrets |
| 배포 | Railway Variables |


### 4.4 리스크

* Key 유출
* 환경변수 누락
* 잘못된 Secret

---

## 5. 모니터링 / 로깅

### 5.1 결론

MVP에서는 **Railway 로그 + 구조화된 애플리케이션 로그**를 사용한다.


### 5.3 MVP 기록 항목

* Agent 행동
* Event 발생
* LLM 호출
* 오류 로그
* 응답 시간

로그 레벨: INFO / WARNING / ERROR

### 5.4 현재 채택

* Railway Logs
* Python Logging
* Agent Trace 로그

