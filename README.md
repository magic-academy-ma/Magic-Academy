# Magic-Academy

AI 학생들이 살아가는 마법학교에서 관계, 조직, 사건이 스스로 만들어지는 Multi-Agent 시뮬레이션

## 로컬 실행

저장소 루트에서 환경변수 파일을 만들고 `POSTGRES_PASSWORD`에 로컬 개발용 비밀번호를 설정합니다.
`JWT_SECRET`에도 충분히 긴 로컬 서명 키를 설정해야 합니다.

```bash
cp .env.example .env
```

그런 다음 전체 개발 환경을 실행합니다.

```bash
docker compose up -d --build
```

PostgreSQL은 호스트의 `127.0.0.1`에만 공개됩니다. 컨테이너 간 연결에는 Compose 내부 네트워크를 사용합니다.

### PostgreSQL 영속 볼륨 주의사항

`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`는 `pgdata` 볼륨을 처음 생성할 때만 적용됩니다. 기존 볼륨을 유지한 채 `.env` 값만 변경하면 PostgreSQL 내부 자격증명은 바뀌지 않아 Backend 연결이 실패할 수 있습니다.

`vector` 확장 초기화 스크립트도 새 볼륨을 처음 생성할 때만 실행됩니다. 기존 `pgdata` 볼륨을 유지하는 경우에는 대상 데이터베이스에 접속해 `CREATE EXTENSION IF NOT EXISTS vector;`를 직접 실행해야 합니다.

기존 데이터가 필요 없는 로컬 개발 환경에서는 다음 명령으로 볼륨을 삭제한 뒤 다시 초기화할 수 있습니다.

```bash
docker compose down -v
docker compose up -d --build
```

`docker compose down -v`는 저장된 PostgreSQL 데이터를 모두 삭제합니다. 보존해야 하는 데이터가 있다면 이 명령을 사용하지 말고 PostgreSQL에서 사용자 비밀번호와 데이터베이스를 직접 마이그레이션한 뒤 `.env`를 변경해야 합니다.

### Backend

```bash
cp .env.example .env
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

서버 실행 후 다음 경로에서 동작을 확인할 수 있습니다.

- Health check: http://localhost:8000/health
- Swagger UI: http://localhost:8000/docs
- API base URL: http://localhost:8000/v1

Backend는 도메인 중심 모듈 구조를 사용합니다.

Backend 컨테이너는 시작할 때 `alembic upgrade head`를 실행합니다. 기존
Simulation 행이 있는 DB에 owner migration을 처음 적용할 때는 자동 소유자를
배정하지 않고 중단하므로, 사용자별 `owner_id` backfill이 먼저 필요합니다.

### 테스트

```bash
docker compose exec backend python -m pytest -q
docker compose exec frontend npm run lint
docker compose exec frontend npm run test -- --run
docker compose exec frontend npm run build
npm --prefix frontend run test:e2e
```

```text
backend/app/
├── main.py          # FastAPI 진입점
├── api/             # HTTP 및 WebSocket 라우터
├── core/            # 환경설정, DB 연결, 미들웨어
├── domain/          # 도메인 모델
├── repositories/    # 데이터베이스 접근
├── services/        # 유즈케이스 조합
└── simulation/      # 시뮬레이션 엔진
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 으로 접속합니다.

## Langfuse Tracing (선택)

Tracing은 기본 비활성화입니다. Python SDK `5.0.4`와 Langfuse Cloud를 사용합니다.
로컬 Python은 3.11 이상이 필요하며, Docker의 Python 3.14에서도 지원됩니다.

개발용 `.env`에 `LANGFUSE_ENABLED=true`, `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`을 설정하세요. Base URL에는 발급받은
Cloud 프로젝트의 리전 URL을 사용하세요. 키는 커밋하거나 로그에 출력하지 않습니다.
Pydantic Settings는 저장소 루트 `.env`를 읽고, Docker Compose는 같은 변수들을
backend 컨테이너에 전달합니다. 변경 후 서버/컨테이너를 재시작하세요.
`LANGFUSE_ENABLED=false` 또는 빈 값으로 끄며, 키 누락/잘못된 URL이면 계측만
비활성화하고 고정된 경고를 남깁니다. 잘못된 활성화 값도 비활성화로 처리합니다.
SDK 초기화는 서버 lifespan에서 한 번 수행하고 종료 시 flush/shutdown합니다.
인증 실패나 전송 장애는 시뮬레이션 결과/DB 트랜잭션을 변경하지 않습니다.

수집 필드:

- Tick: simulation_id, tick_number, status, duration_ms
- Agent: run_id, agent_id, tick_number, model, prompt_version, action_type,
  runtime_status(PROPOSED/FALLBACK/SKIPPED), retry_count, 정규화한 failure_reason
- 호출 시도/검증: attempt_number, is_retry, provider, 검증/호출 실패 구분
- Anthropic Generation: 모델, 성공/실패, 지연 시간, 응답에 존재하는 실제
  input/output/cache read/cache creation token 수

제외: 사용자 입력, 메모리, 프롬프트, LLM 응답 전문, 이름/성격/상태 본문,
예외 메시지·스택, 키/인증 토큰. 예외 타입명만 failure_type으로 기록합니다. 수동 계측만 사용하며 provider 자동 계측과
LangChain callback을 등록하지 않습니다. 별도 tracer provider와 SDK scope 필터로
자동 계측 span을 export하지 않습니다. SDK가 scope에 추가하는 public key도
export 직전에 제거하며, 키는 Cloud 인증 헤더에만 사용합니다. Mock은 `provider=mock`인 호출 시도로
구분하고 Generation을 만들지 않습니다. 토큰 누락 시 사용량을 기록하지 않으며
비용은 애플리케이션에서 계산하지 않습니다. Cloud가 모델 가격으로 표시하는
비용은 Langfuse 측 추산일 수 있습니다.

수동 Cloud 수신 검증 (API 키 발급 및 대시보드 조작은 개발자가 직접 수행):

1. 키와 리전 URL 설정 후 backend를 재시작하고 기존 UI/API에서 Tick을 실행합니다.
2. Langfuse Traces에서 `tick`을 찾고 simulation_id/tick_number로 대조합니다.
   하위 `tick.engine` → 여러 `agent.runtime` → `llm.attempt` →
   `anthropic.generate`를 확인합니다. 검증은 `llm.validation` 형제 span입니다.
3. 같은 Tick의 Agent가 같은 trace에 있고 각 호출은 자신의 Agent에 속하는지,
   호출 시도당 Generation이 하나인지, 모델·토큰·지연 시간과 최종 상태를 확인합니다.
   SDK 내부 HTTP retry는 하나의 generate에 포함됩니다.
4. 실패 fixture/테스트에서 retry의 is_retry, 검증 실패, FALLBACK, SKIPPED,
   quota_exceeded를 확인합니다. SKIPPED/quota 거절에는 Generation이 없어야 합니다.
5. input/output 및 예외 이벤트에 원문이 없는지 확인합니다. Replay/복구 시 새 LLM
   호출이 없어야 합니다. 비활성화 후 새 trace 전송이 없는지도 확인합니다.
6. 잘못된 수신 URL로 전송 장애를 재현해 Tick 결과와 저장 상태가 같은지 확인합니다.
   장애 중 trace 유실은 허용하며 durable queue나 재전송 보장은 제공하지 않습니다.

Cloud 수신은 API 키 없이 자동 검증하지 않습니다. 자동 테스트는 가짜 provider와
메모리 exporter로 외부 호출 없이 계층/사용량/실패 격리를 검증합니다.

현재 검증 범위:

- 검증 완료: Langfuse Cloud 인증, Mock Tick의 실제 Cloud 수신, Tick → Agent →
  호출 시도 계층, 원문·키 제외, 격리된 테스트 DB에서 전체 회귀 테스트.
- 미검증: 실제 Anthropic Generation 및 실제 Claude 응답의 토큰 사용량.
  `ANTHROPIC_API_KEY`가 없어 유료 모델 호출은 수행하지 않았습니다.
  가짜 provider 응답 기반 Generation·사용량 테스트와 실제 API 검증은 구분합니다.
- 별도 로컬 환경 문제: 기존 PostgreSQL 비밀번호 인증 불일치로 일반 Compose
  backend 기동이 실패했습니다. 기존 DB·볼륨·자격증명은 변경하지 않았으며,
  격리된 테스트 DB의 검증 결과를 사용합니다.

공식 참고: [SDK 개요](https://langfuse.com/docs/observability/sdk/overview),
[v5 호환성](https://langfuse.com/docs/observability/sdk/upgrade-path/python-v4-to-v5),
[수동 계측](https://langfuse.com/docs/observability/sdk/instrumentation).
