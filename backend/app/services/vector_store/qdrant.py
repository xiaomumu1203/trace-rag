from typing import Any, cast

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.services.vector_store.base import BaseVectorStore
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from app.core.config import settings


class QdrantStore(BaseVectorStore):

    def __init__(self, collection_name: str, embedding_function: Embeddings,**kwargs):
        self._client = QdrantClient(
            url=settings.QDRANT_URL,
            prefer_grpc=settings.QDRANT_PREFER_GRPC,
        )
        self._collection_name = collection_name
        self._store = QdrantVectorStore(
            client=self._client,
            collection_name=collection_name,
            embedding=embedding_function,
        )

    def add_documents(self, documents: list[Document]) -> None:
        """向量库添加文档"""
        self._store.add_documents(documents)

    def delete(self, ids: list[str]) -> None:
        """从向量库中删除文档"""
        qdrant_ids = cast(list[str | int], ids)
        self._store.delete(ids=qdrant_ids)

    def as_retriever(self, **kwargs: Any):
        """返回检索器"""
        return self._store.as_retriever(**kwargs)

    def similarity_search(self, query: str, k: int = 5, **kwargs) -> list[Document]:
        """执行相似性搜索"""
        return self._store.similarity_search(query, k=k, **kwargs)

    def similarity_search_with_score(self, query: str, k: int = 5, **kwargs) -> list[tuple[Document, float]]:
        """执行相似性搜索并返回分数"""
        return self._store.similarity_search_with_score(query, k=k, **kwargs)

    def delete_collection(self) -> None:
        """删除向量库"""
        self._client.delete_collection(self._collection_name)
        
