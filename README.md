# Magic-Academy

AI 학생들이 살아가는 마법학교에서 관계, 조직, 사건이 스스로 만들어지는 Multi-Agent 시뮬레이션

## 로컬 실행

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
