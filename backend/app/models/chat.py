from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, Table, Column
from sqlalchemy.dialects.mysql import LONGTEXT
from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .knowledge_base import KnowledgeBase

chat_knowledge_bases = Table(
    "chat_knowledge_bases",
    Base.metadata,
    Column("chat_id", Integer, ForeignKey("chats.id"), primary_key=True),
    Column("knowledge_base_id", Integer, ForeignKey("knowledge_bases.id"), primary_key=True),
)

class Chat(Base,TimestampMixin):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationship to User
    user: Mapped["User"] = relationship("User", back_populates="chats")
    # Relationship to Message
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    # Relationship to KnowledgeBase
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship("KnowledgeBase", secondary=chat_knowledge_bases, back_populates="chats")


class Message(Base,TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[int] = mapped_column(Integer,ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    # Relationship to Chat
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
