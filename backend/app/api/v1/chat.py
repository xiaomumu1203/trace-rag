import base64
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session


from app.schemas.chat import ChatCreate, ChatResponse, MessageResponse
from app.services.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase
from app.models.chat import Chat, Message
from app.services.chat_services import generate_response
from app.services.chat_memory import chat_memory

router = APIRouter()

CONTEXT_SEPARATOR = "__LLM_RESPONSE__"


def extract_answer_and_sources(content: str) -> tuple[str, list[dict[str, Any]]]:
    """Extract persisted retrieval sources while keeping legacy messages readable."""
    if CONTEXT_SEPARATOR not in content:
        return content, []

    encoded_context, answer = content.split(CONTEXT_SEPARATOR, 1)
    try:
        payload = json.loads(base64.b64decode(encoded_context).decode("utf-8"))
        raw_sources = payload.get("context", [])
        if not isinstance(raw_sources, list):
            return answer, []

        sources = []
        for index, source in enumerate(raw_sources, start=1):
            if not isinstance(source, dict):
                continue
            metadata = source.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            normalized = {
                **source,
                "index": source.get("index", index),
                "metadata": metadata,
                "knowledge_base_name": source.get("knowledge_base_name"),
                "file_name": source.get("file_name") or metadata.get("file_name"),
            }
            sources.append(normalized)
        return answer, sources
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return answer, []

@router.post("/",response_model=ChatResponse)
async def create_chat(
    *,
    db: Session = Depends(get_db),
    chat_in: ChatCreate,
    current_user: User = Depends(get_current_user),
)-> Any:
    """
    证明知识库存在属于当前用户的聊天记录，并创建一个新的聊天记录
    """
    knowledge_bases = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id.in_(chat_in.chat_knowledge_base_ids),
            KnowledgeBase.user_id == current_user.id
        ).all()
    )
    if len(knowledge_bases) != len(chat_in.chat_knowledge_base_ids):
        raise HTTPException(
            status_code=400, 
            detail="某些知识库不存在或不属于当前用户"
        )
    chat = Chat(
        title=chat_in.title,
        user_id=current_user.id,
    )
    chat.knowledge_bases = knowledge_bases
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat

@router.get("/", response_model=list[ChatResponse])
async def get_chats(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100
)-> Any:
    chats = (
        db.query(Chat)
        .filter(Chat.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return chats

@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    *,
    db: Session = Depends(get_db),
    chat_id: int,
    current_user: User = Depends(get_current_user),
)-> Any:
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == current_user.id)
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="聊天记录不存在")
    return chat

@router.get("/{chat_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    *,
    db: Session = Depends(get_db),
    chat_id: int,
    current_user: User = Depends(get_current_user),
)-> Any:
    """返回当前用户会话中的历史消息。"""
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == current_user.id)
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    messages = (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.id.asc())
        .all()
    )
    responses = []
    for message in messages:
        content, sources = extract_answer_and_sources(message.content)
        response = MessageResponse.model_validate(message)
        responses.append(response.model_copy(update={"content": content, "sources": sources}))
    return responses

@router.post("/{chat_id}/messages")
async def create_message(
    *,
    db: Session = Depends(get_db),
    chat_id: int,
    messages: dict,
    current_user: User = Depends(get_current_user),
)-> StreamingResponse:
    """
    创建一个新的消息记录
    """
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == current_user.id)
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="聊天记录不存在")

    #获得最近的消息记录
    last_message = messages["messages"][-1]
    if last_message["role"] != "user":
        raise HTTPException(status_code=400, detail="最新一条消息记录是用户消息，不能再创建新的用户消息")

    #获得知识库id列表
    knowledge_base_ids = [kb.id for kb in chat.knowledge_bases]
    
    
    async def response_stream():
        async for chunk in generate_response(
            query = last_message["content"],
            knowledge_base_ids = knowledge_base_ids,
            chat_id = chat_id,
            user_id = current_user.id,
            db = db,
        ):
            yield chunk

    return StreamingResponse(
        response_stream(), 
        media_type="text/event-stream",
        headers={
            "x-vercel-ai-data-stream": "v1",
        }
    )

@router.delete("/{chat_id}")
async def delete_chat(
    *,
    db: Session = Depends(get_db),
    chat_id: int,
    current_user: User = Depends(get_current_user),
)-> Any:
    """
    删除一个聊天记录
    """
    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == current_user.id)
        .first()
    )
    if not chat:
        raise HTTPException(status_code=404, detail="聊天记录不存在")
    
    db.delete(chat)
    db.commit()
    await chat_memory.delete(chat_id)
    return {"status": "success"}
