import os

import psycopg
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.api.students import router as students_router

app = FastAPI(title="Magic Academy", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(students_router)


@app.get("/health")
def health() -> dict[str, str]:
    try:
        with psycopg.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            dbname=os.environ.get("DB_NAME", "magic_academy"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD"),
            connect_timeout=3,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except (psycopg.Error, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return {"status": "ok", "database": "ok"}
