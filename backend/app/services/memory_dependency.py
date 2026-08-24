"""Slice 3: manual_tick.py / API 레이어에서 사용할 Memory 콜백 의존성.

OPENAI_API_KEY가 설정되지 않은 경우 memory 기능을 생략하고 Tick은 정상 진행되도록
(None, None)을 반환한다.
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.repositories.memory_repository import MemoryRepository
from app.services.embedding_service import build_embedding_client
from app.services.memory_adapter import build_memory_retriever, build_memory_store
from app.simulation.tick_engine import MemoryRetrieverFn, MemoryStoreFn


def create_memory_hooks(
    settings: Settings, session: Session
) -> tuple[MemoryRetrieverFn | None, MemoryStoreFn | None]:
    if not settings.openai_api_key or not settings.openai_api_key.strip():
        return None, None
    embedding_client = build_embedding_client()
    repo = MemoryRepository()
    return (
        build_memory_retriever(session, repo, embedding_client),
        build_memory_store(session, repo, embedding_client),
    )


def get_memory_hooks(
    db: Session = Depends(get_db),
) -> tuple[MemoryRetrieverFn | None, MemoryStoreFn | None]:
    return create_memory_hooks(get_settings(), db)
