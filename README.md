# Magic-Academy

AI 학생들이 살아가는 마법학교에서 관계, 조직, 사건이 스스로 만들어지는 Multi-Agent 시뮬레이션

## 로컬 실행

저장소 루트에서 환경변수 파일을 만들고 `POSTGRES_PASSWORD`에 로컬 개발용 비밀번호를 설정합니다.

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
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

서버 실행 후 http://localhost:8000/health 에서 동작을 확인할 수 있습니다.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

브라우저에서 http://localhost:5173 으로 접속합니다.
