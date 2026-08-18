from typing import Any

from pydantic import BaseModel,Field,ConfigDict


class MessageBase(BaseModel):
    content: str = Field(..., description="消息内容")
    role: str = Field(..., description="消息角色，user、assistant、system")

class MessageCreate(MessageBase):
    chat_id: int = Field(..., description="聊天ID")

class MessageUpdate(MessageBase):
    chat_id: int = Field(..., description="聊天ID")

class CitationSource(BaseModel):
    index: int
    page_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    knowledge_base_name: str | None = None
    file_name: str | None = None

class MessageResponse(MessageBase):
    id: int = Field(..., description="消息ID")
    chat_id: int = Field(..., description="聊天ID")
    sources: list[CitationSource] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)





class ChatBase(BaseModel):
    title: str = Field(..., description="聊天名称")

class ChatCreate(ChatBase):
    chat_knowledge_base_ids: list[int] = Field(..., description="关联的知识库ID列表")

class ChatUpdate(ChatBase):
    chat_knowledge_base_ids: list[int] | None = Field(None, description="关联的知识库ID列表")

class ChatResponse(ChatBase):
    id: int = Field(..., description="聊天ID")
    user_id: int = Field(..., description="用户ID")
    title: str = Field(..., description="聊天标题")
    chat_knowledge_base_ids: list[int] | None = Field(None, description="关联的知识库ID列表")

    model_config = ConfigDict(from_attributes=True)

