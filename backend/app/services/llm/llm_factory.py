import json
from typing import Any, Optional
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from app.core.config import settings

class LLMFactory:
    @staticmethod
    def with_structured_output(llm: BaseChatModel, schema: Any):
        """Create a structured-output runnable compatible with the active provider."""
        if isinstance(llm, ChatDeepSeek):
            # DeepSeek thinking models reject the tool_choice parameter used by the
            # default function-calling strategy. JSON mode does not use tools.
            return llm.with_structured_output(schema, method="json_mode")
        return llm.with_structured_output(schema)

    @staticmethod
    def json_schema_instruction(schema: Any) -> str:
        """Give JSON-mode models the schema that function calling normally supplies."""
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        return f"Return only valid JSON matching this JSON Schema: {schema_json}"

    @staticmethod
    def create(
        provider:Optional[str] = None,
        temperature: float = 0,
        streaming: bool =True,
    ) -> BaseChatModel:
        """
        创建LLM模型实例
        """
        provider = provider or settings.CHAT_PROVIDER
        if provider.lower() == "openai":
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("your-"):
                raise ValueError("OPENAI_API_KEY 未配置，请在 .env 中填写有效的 API Key")
            return ChatOpenAI(
                model=settings.OPENAI_MODEL,
                api_key=SecretStr(settings.OPENAI_API_KEY),
                base_url=settings.OPENAI_API_BASE,
                temperature=temperature,
                streaming=streaming,
            )
        elif provider.lower() == "deepseek":
            if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY.startswith("your-"):
                raise ValueError("DEEPSEEK_API_KEY 未配置，请在 .env 中填写有效的 API Key")
            return ChatDeepSeek(
                model=settings.DEEPSEEK_MODEL,
                api_key=SecretStr(settings.DEEPSEEK_API_KEY),
                base_url=settings.DEEPSEEK_API_BASE,
                temperature=temperature,
                streaming=streaming,
            )

        else:
            raise ValueError(f"未知的 LLM 供应商: {provider}")
