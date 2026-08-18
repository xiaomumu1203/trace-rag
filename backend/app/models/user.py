from typing import TYPE_CHECKING
from .base import Base, TimestampMixin
from sqlalchemy import String, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column

if TYPE_CHECKING:
    from .api_key import APIKey
    from .chat import Chat
    from .knowledge_base import KnowledgeBase

class User(Base,TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True,nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True,nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationship to Chat
    chats: Mapped[list["Chat"]] = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    # Relationship to APIKey
    api_keys: Mapped[list["APIKey"]] = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    # Relationship to KnowledgeBase
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship("KnowledgeBase", back_populates="user", cascade="all, delete-orphan")