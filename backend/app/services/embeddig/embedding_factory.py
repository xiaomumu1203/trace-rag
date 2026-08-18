from functools import lru_cache

from langchain_community.embeddings import DashScopeEmbeddings, HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from app.core.config import settings


class EmbeddingFactory:
    @staticmethod
    @lru_cache(maxsize=1)
    def create():
        """
        创建Embeddings模型实例
        """
        provider = settings.EMBEDDINGS_PROVIDER.lower()

        if provider.lower() == "huggingface":
            model_kwargs = {}
            if settings.HUGGINGFACE_API_KEY:
                model_kwargs["token"] = settings.HUGGINGFACE_API_KEY
            return HuggingFaceEmbeddings(
                model_name=settings.HUGGINGFACE_EMBEDDINGS_MODEL,
                model_kwargs=model_kwargs
            )
        elif provider.lower() == "openai":
            return OpenAIEmbeddings(
                model=settings.OPENAI_EMBEDDINGS_MODEL,
                api_key=SecretStr(settings.OPENAI_API_KEY),
            )
        elif provider.lower() in ("dashscope", "dashcope"):
            return DashScopeEmbeddings(
                model=settings.DASH_SCOPE_EMBEDDINGS_MODEL,
                dashscope_api_key=settings.DASH_SCOPE_API_KEY,
            )
        else:
            raise ValueError(f"未知的 Embeddings 供应商: {provider}")
