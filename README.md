# Magic-Academy

AI 학생들이 살아가는 마법학교에서 관계, 조직, 사건이 스스로 만들어지는 Multi-Agent 시뮬레이션

## 로컬 실행

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
