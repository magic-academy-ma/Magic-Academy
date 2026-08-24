import pytest

from app.core.config import Settings
from app.services import memory_dependency
from app.services.memory_dependency import create_memory_hooks


def settings(**overrides):
    return Settings(
        jwt_secret="test-secret-key-minimum-32-characters-long",
        **overrides,
    )


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_create_memory_hooks_returns_none_pair_when_api_key_missing(api_key):
    retriever, store = create_memory_hooks(settings(openai_api_key=api_key), session=object())

    assert retriever is None
    assert store is None


def test_create_memory_hooks_builds_callables_when_api_key_configured(monkeypatch):
    class FakeEmbeddingClient:
        pass

    monkeypatch.setattr(
        memory_dependency, "build_embedding_client", lambda: FakeEmbeddingClient()
    )

    retriever, store = create_memory_hooks(
        settings(openai_api_key="test-openai-key"), session=object()
    )

    assert callable(retriever)
    assert callable(store)
