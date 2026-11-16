from langchain_core.documents import Document

from app.services.hybrid_retriever import HybridRetriever, tokenize


class FakeVectorStore:
    def __init__(self, documents: list[Document]):
        self.documents = documents

    def similarity_search(self, query: str, k: int) -> list[Document]:
        return self.documents[:k]


def document(chunk_id: str, content: str) -> Document:
    return Document(page_content=content, metadata={"chunk_id": chunk_id})


def test_tokenize_supports_chinese_and_latin_text() -> None:
    tokens = tokenize("检索 RAG 系统")

    assert "检索" in tokens
    assert "rag" in tokens


def test_dense_search_interleaves_knowledge_bases_and_removes_duplicates() -> None:
    retriever = HybridRetriever(
        vector_stores=[
            FakeVectorStore([document("a", "A"), document("duplicate", "D")]),
            FakeVectorStore([document("b", "B"), document("duplicate", "D")]),
        ],
        db=None,
        knowledge_base_ids=[1, 2],
        candidate_k=2,
    )

    results = retriever._dense_search("anything")

    assert [item.metadata["chunk_id"] for item in results] == ["a", "b", "duplicate"]


def test_rrf_prioritizes_a_chunk_found_by_both_retrievers() -> None:
    retriever = HybridRetriever(vector_stores=[], db=None, knowledge_base_ids=[], final_k=3, rrf_k=60)

    results = retriever._rrf_fuse(
        [document("shared", "Shared"), document("dense-only", "Dense")],
        [document("lexical-only", "Lexical"), document("shared", "Shared")],
    )

    assert [item.metadata["chunk_id"] for item in results] == ["shared", "lexical-only", "dense-only"]
    assert results[0].metadata["dense_rank"] == 1
    assert results[0].metadata["bm25_rank"] == 2


def test_retrieve_can_select_dense_or_bm25_without_running_rrf(monkeypatch) -> None:
    retriever = HybridRetriever(vector_stores=[], db=None, knowledge_base_ids=[], final_k=1)
    dense = [document("dense", "Dense")]
    bm25 = [document("bm25", "BM25")]
    monkeypatch.setattr(retriever, "_dense_search", lambda query: dense)
    monkeypatch.setattr(retriever, "_bm25_search", lambda query: bm25)

    dense_results = retriever.retrieve("query", strategy="dense")
    bm25_results = retriever.retrieve("query", strategy="bm25")

    assert [item.metadata["chunk_id"] for item in dense_results] == ["dense"]
    assert dense_results[0].metadata["dense_rank"] == 1
    assert "rrf_score" not in dense_results[0].metadata
    assert [item.metadata["chunk_id"] for item in bm25_results] == ["bm25"]
    assert bm25_results[0].metadata["bm25_rank"] == 1


def test_bm25_strategy_skips_dense_search(monkeypatch) -> None:
    retriever = HybridRetriever(vector_stores=[], db=None, knowledge_base_ids=[], final_k=1)

    def fail(query: str) -> list[Document]:
        raise AssertionError("dense search must not run for the bm25 strategy")

    monkeypatch.setattr(retriever, "_bm25_search", lambda query: [document("bm25", "BM25")])
    monkeypatch.setattr(retriever, "_dense_search", fail)

    results = retriever.retrieve("query", strategy="bm25")

    assert [item.metadata["chunk_id"] for item in results] == ["bm25"]
