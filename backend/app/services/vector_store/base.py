from abc import ABC, abstractmethod
from typing import Any, List
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


class BaseVectorStore(ABC):

    @abstractmethod
    def __init__(self, collection_name: str, embedding_function :Embeddings, **kwargs):
        """初始化向量存储"""
        pass

    @abstractmethod
    def add_documents(self, documents:List[Document]) -> None:
        """添加文档到向量存储"""
        pass

    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """从向量存储中删除文档"""
        pass

    @abstractmethod
    def as_retriever(self, **kwargs: Any) -> Any:
        """返回检索器"""
        pass

    @abstractmethod
    def similarity_search(self, query: str, k: int = 5, **kwargs: Any)-> List[Document]:
        """执行相似性搜索"""
        pass

    @abstractmethod
    def similarity_search_with_score(self, query: str, k: int = 5, **kwargs: Any) -> List[tuple[Document, float]]:
        """执行相似性搜索并返回分数"""
        pass

    @abstractmethod
    def delete_collection(self) -> None:
        """删除向量存储"""
        pass