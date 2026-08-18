"""Redis-backed recent chat memory with MySQL fallback."""

from __future__ import annotations

import json
import logging

from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.chat import Message

logger = logging.getLogger(__name__)

CONTEXT_SEPARATOR = "__LLM_RESPONSE__"


def _answer_only(content: str) -> str:
    """Remove persisted retrieval metadata before sending history to the LLM."""
    if CONTEXT_SEPARATOR not in content:
        return content
    _, answer = content.split(CONTEXT_SEPARATOR, 1)
    return answer


class ChatMemory:
    def __init__(self) -> None:
        self._redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    @staticmethod
    def _key(chat_id: int) -> str:
        return f"chat:{chat_id}:recent_messages"

    async def get_or_load(self, chat_id: int, db: Session) -> list[dict[str, str]]:
        """Read recent history from Redis, falling back to durable MySQL messages."""
        try:
            cached = await self._redis.lrange(self._key(chat_id), 0, -1)
            if cached:
                return [json.loads(item) for item in cached]
        except Exception as exc:
            logger.warning("Redis chat-memory read failed; using MySQL: %s", exc)

        rows = (
            db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.id.desc())
            .limit(settings.CHAT_MEMORY_MAX_MESSAGES)
            .all()
        )
        history = [
            {"role": row.role, "content": _answer_only(row.content)}
            for row in reversed(rows)
        ]
        if history:
            await self.replace(chat_id, history)
        return history

    async def append(self, chat_id: int, role: str, content: str) -> None:
        payload = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.rpush(self._key(chat_id), payload)
                pipe.ltrim(self._key(chat_id), -settings.CHAT_MEMORY_MAX_MESSAGES, -1)
                pipe.expire(self._key(chat_id), settings.CHAT_MEMORY_TTL_SECONDS)
                await pipe.execute()
        except Exception as exc:
            logger.warning("Redis chat-memory write failed: %s", exc)

    async def replace(self, chat_id: int, history: list[dict[str, str]]) -> None:
        if not history:
            return
        values = [json.dumps(item, ensure_ascii=False) for item in history]
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.delete(self._key(chat_id))
                pipe.rpush(self._key(chat_id), *values)
                pipe.ltrim(self._key(chat_id), -settings.CHAT_MEMORY_MAX_MESSAGES, -1)
                pipe.expire(self._key(chat_id), settings.CHAT_MEMORY_TTL_SECONDS)
                await pipe.execute()
        except Exception as exc:
            logger.warning("Redis chat-memory refresh failed: %s", exc)

    async def delete(self, chat_id: int) -> None:
        try:
            await self._redis.delete(self._key(chat_id))
        except Exception as exc:
            logger.warning("Redis chat-memory delete failed: %s", exc)

    async def close(self) -> None:
        await self._redis.aclose()


chat_memory = ChatMemory()
