
from typing import Dict, Type

from langchain_core.embeddings import Embeddings
from app.services.vector_store.chroma import ChromaVectorStore
from app.services.vector_store.base import BaseVectorStore
from app.services.vector_store.qdrant import QdrantStore


class VectorStoreFactory:

    _stores: Dict[str, Type[BaseVectorStore]] = {
        'chroma': ChromaVectorStore,
        'qdrant': QdrantStore,
    }

    @classmethod
    def create(
        cls,
        store_type: str,
        collection_name: str,
        embeddings_function: Embeddings,
        **kwargs,
    ) -> BaseVectorStore:
        """
        创建向量存储实例
        
        Args:
            store_type (str): 向量存储类型
            collection_name (str): 集合名称
            embeddings_function (Embeddings): 嵌入函数
            **kwargs: 其他参数
        
        Returns:
            BaseVectorStore: 向量存储实例
        """

        store_class = cls._stores.get(store_type.lower())
        if not store_class:
            raise ValueError(
                f"未知的向量存储类型: {store_type}。"
                f"可用类型: {', '.join(cls._stores.keys())}"
            )
        
        return store_class(
            collection_name=collection_name,
            embedding_function=embeddings_function,
            **kwargs
        )
    

    @classmethod
    def register_store(cls, name: str, store_class: Type[BaseVectorStore])-> None:
        """
        注册向量存储
        Args:
            name (str): 向量存储名称
            store_class (Type[BaseVectorStore]): 向量存储类
        """
        cls._stores[name.lower()] = store_class
