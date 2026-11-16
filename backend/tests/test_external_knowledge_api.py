from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langchain_core.documents import Document

from app.api.external import knowledge as external_knowledge
from app.services import auth
from app.services.api_key import APIKeyService


class FakeQuery:
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.knowledge_base


class FakeSession:
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base

    def query(self, *args, **kwargs):
        return FakeQuery(self.knowledge_base)


def test_api_key_dependency_rejects_missing_key() -> None:
    with pytest.raises(HTTPException) as error:
        auth.get_api_key_user(db=object(), api_key=None)

    assert error.value.status_code == 401


def test_api_key_dependency_rejects_unknown_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(APIKeyService, "get_api_key_by_key", lambda **kwargs: None)

    with pytest.raises(HTTPException) as error:
        auth.get_api_key_user(db=object(), api_key="sk-not-found")

    assert error.value.status_code == 401


def test_api_key_dependency_returns_key_owner_and_updates_last_used(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id=7)
    api_key = SimpleNamespace(user=user)
    updated_keys = []
    monkeypatch.setattr(APIKeyService, "get_api_key_by_key", lambda **kwargs: api_key)
    monkeypatch.setattr(
        APIKeyService,
        "update_last_used",
        lambda **kwargs: updated_keys.append(kwargs["api_key"]),
    )

    current_user = auth.get_api_key_user(db=object(), api_key="sk-valid")

    assert current_user is user
    assert updated_keys == [api_key]


def test_external_query_returns_retrieval_result_for_owned_knowledge_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    knowledge_base = SimpleNamespace(id=3, user_id=7)
    document = Document(
        page_content="TraceRAG 使用 RRF 融合检索结果。",
        metadata={"rrf_score": 0.03, "dense_rank": 1, "bm25_rank": 2},
    )

    class FakeRetriever:
        def __init__(self, **kwargs):
            pass

        def invoke(self, query: str):
            return [document]

    monkeypatch.setattr(external_knowledge.EmbeddingFactory, "create", lambda: object())
    monkeypatch.setattr(external_knowledge.VectorStoreFactory, "create", lambda **kwargs: object())
    monkeypatch.setattr(external_knowledge, "HybridRetriever", FakeRetriever)

    response = external_knowledge.query_knowledge_base(
        db=FakeSession(knowledge_base),
        knowledge_base_id=3,
        query="RRF 是什么？",
        top_k=3,
        current_user=SimpleNamespace(id=7),
    )

    assert response["results"][0]["content"] == document.page_content
    assert response["results"][0]["dense_rank"] == 1
    assert response["results"][0]["bm25_rank"] == 2


def test_external_query_hides_a_knowledge_base_owned_by_another_user() -> None:
    with pytest.raises(HTTPException) as error:
        external_knowledge.query_knowledge_base(
            db=FakeSession(knowledge_base=None),
            knowledge_base_id=99,
            query="不应访问到其他用户的数据",
            top_k=3,
            current_user=SimpleNamespace(id=7),
        )

    assert error.value.status_code == 404
