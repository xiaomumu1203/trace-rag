from typing import Any

import chromadb
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app.core.config import settings
from app.services.vector_store.base import BaseVectorStore


class ChromaVectorStore(BaseVectorStore):

    def __init__(self, collection_name: str, embedding_function: Embeddings, **kwargs: Any):
       chroma_client = chromadb.HttpClient(
           host=settings.CHROMA_DB_HOST,
           port=settings.CHROMA_DB_PORT,
       )

       self._store = Chroma(
           client=chroma_client,
           collection_name=collection_name,
           embedding_function=embedding_function,
       )

    def add_documents(self, documents: list[Document]) -> None:
        """向量库添加文档"""
        self._store.add_documents(documents)

    def delete(self, ids: list[str]) -> None:
        """从向量库中删除文档"""
        self._store.delete(ids)

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
        self._store._client.delete_collection(self._store._collection.name)