"""Slice 3 Task 5: OpenAI embedding client 단위 테스트 — 실제 API는 mock으로 대체"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.embedding_service import OpenAIEmbeddingClient


def make_openai_response(vector: list[float]):
    data_item = MagicMock()
    data_item.embedding = vector
    response = MagicMock()
    response.data = [data_item]
    return response


async def test_embed_calls_openai_with_configured_model():
    fake_vector = [0.1] * 1536
    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(return_value=make_openai_response(fake_vector))

    client = OpenAIEmbeddingClient(client=mock_client, model="text-embedding-3-small")
    result = await client.embed("협력적인 대화를 나눴다")

    assert result == fake_vector
    mock_client.embeddings.create.assert_awaited_once_with(
        model="text-embedding-3-small",
        input="협력적인 대화를 나눴다",
    )


async def test_embed_raises_on_empty_text():
    mock_client = MagicMock()
    client = OpenAIEmbeddingClient(client=mock_client, model="text-embedding-3-small")

    with pytest.raises(ValueError):
        await client.embed("")


async def test_embed_wraps_openai_errors():
    mock_client = MagicMock()
    mock_client.embeddings.create = AsyncMock(side_effect=RuntimeError("api down"))
    client = OpenAIEmbeddingClient(client=mock_client, model="text-embedding-3-small")

    with pytest.raises(RuntimeError, match="embedding 생성 실패"):
        await client.embed("텍스트")
