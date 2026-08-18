"""Lexical + dense retrieval combined with Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from collections import defaultdict
from itertools import zip_longest
from typing import Any, Iterable

import jieba
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from app.models.knowledge_base import DocumentChunk


def tokenize(text: str) -> list[str]:
    """Tokenize Chinese and Latin text for BM25 without changing source text."""
    return [token.lower() for token in jieba.lcut(text) if token.strip() and not token.isspace()]


class HybridRetriever(BaseRetriever):
    """Retrieve dense and BM25 candidates, then fuse their ranks with RRF.

    Rank fusion deliberately avoids adding raw scores: vector-store distances and
    BM25 scores have different scales and are not directly comparable.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_stores: list[Any]
    db: Any
    knowledge_base_ids: list[int]
    candidate_k: int = 20
    final_k: int = 3
    rrf_k: int = 60

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        dense_results = self._dense_search(query)
        bm25_results = self._bm25_search(query)
        return self._rrf_fuse(dense_results, bm25_results)

    def _dense_search(self, query: str) -> list[Document]:
        """Retrieve candidates from every selected knowledge base."""
        per_store_results = [store.similarity_search(query, k=self.candidate_k) for store in self.vector_stores]
        results = [document for group in zip_longest(*per_store_results) for document in group if document]
        return self._deduplicate(results)

    def _bm25_search(self, query: str) -> list[Document]:
        session: Session = self.db
        chunks = (
            session.query(DocumentChunk)
            .filter(
                DocumentChunk.knowledge_base_id.in_(self.knowledge_base_ids),
                DocumentChunk.content.isnot(None),
                DocumentChunk.content != "",
            )
            .all()
        )
        if not chunks:
            return []

        corpus = [tokenize(chunk.content or "") for chunk in chunks]
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scores = BM25Okapi(corpus).get_scores(query_tokens)
        ranked_indexes = sorted(range(len(chunks)), key=lambda index: scores[index], reverse=True)

        results: list[Document] = []
        for index in ranked_indexes[: self.candidate_k]:
            # Zero-score documents are not lexical matches and must not influence RRF.
            if scores[index] <= 0:
                break
            chunk = chunks[index]
            metadata = dict(chunk.chunk_metadata or {})
            metadata.setdefault("chunk_id", chunk.id)
            metadata.setdefault("kb_id", chunk.knowledge_base_id)
            metadata.setdefault("document_id", chunk.document_id)
            metadata.setdefault("file_name", chunk.file_name)
            results.append(Document(page_content=chunk.content or "", metadata=metadata))
        return results

    def _rrf_fuse(
        self, dense_results: Iterable[Document], bm25_results: Iterable[Document]
    ) -> list[Document]:
        scores: dict[str, float] = defaultdict(float)
        documents: dict[str, Document] = {}
        ranks: dict[str, dict[str, int]] = defaultdict(dict)

        for source, result_list in (("dense", dense_results), ("bm25", bm25_results)):
            for rank, document in enumerate(result_list, start=1):
                key = self._document_key(document)
                scores[key] += 1 / (self.rrf_k + rank)
                ranks[key][f"{source}_rank"] = rank
                documents.setdefault(key, document)

        ranked_items = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        ranked_keys = [chunk_id for chunk_id, _ in ranked_items[: self.final_k]]
        fused_documents: list[Document] = []
        for key in ranked_keys:
            document = documents[key]
            # Expose the score for retrieval-test/API consumers without leaking it to prompts.
            document.metadata = {
                **document.metadata,
                **ranks[key],
                "rrf_score": scores[key],
            }
            fused_documents.append(document)
        return fused_documents

    @classmethod
    def _document_key(cls, document: Document) -> str:
        return str(document.metadata.get("chunk_id") or document.page_content)

    @classmethod
    def _deduplicate(cls, documents: Iterable[Document]) -> list[Document]:
        seen: set[str] = set()
        unique: list[Document] = []
        for document in documents:
            key = cls._document_key(document)
            if key not in seen:
                seen.add(key)
                unique.append(document)
        return unique
