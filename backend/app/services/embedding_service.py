"""Slice 3: Memory 후보 텍스트를 OpenAI embedding 벡터로 변환하는 클라이언트"""
from typing import Protocol

from openai import AsyncOpenAI

from app.core.config import get_settings


class EmbeddingClient(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OpenAIEmbeddingClient:
    """OpenAI Embeddings API 래퍼 (text-embedding-3-small, 1536차원 기본)"""

    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("embed() 대상 텍스트는 비어 있을 수 없습니다")
        try:
            response = await self._client.embeddings.create(model=self._model, input=text)
        except Exception as exc:
            raise RuntimeError(f"embedding 생성 실패: {exc}") from exc
        return list(response.data[0].embedding)


def build_embedding_client() -> OpenAIEmbeddingClient:
    """app.core.config 설정에서 OPENAI_API_KEY를 읽어 실제 클라이언트를 구성"""
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다")
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    return OpenAIEmbeddingClient(client=client, model=settings.openai_embedding_model)
