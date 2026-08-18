import sqlalchemy
from typing import Optional, TYPE_CHECKING
from .base import Base, TimestampMixin
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, Text, JSON, BigInteger

if TYPE_CHECKING:
    from .user import User
    from .chat import Chat

class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str|None] = mapped_column(String(500), nullable=True)

    # Relationship to User
    user: Mapped["User"] = relationship("User", back_populates="knowledge_bases")
    # Relationship to Document
    documents: Mapped[list["Document"]] = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    # Relationship to DocumentUpload
    document_uploads: Mapped[list["DocumentUpload"]] = relationship("DocumentUpload", back_populates="knowledge_base", cascade="all, delete-orphan")
    # Relationship to ProcessingTask
    processing_tasks: Mapped[list["ProcessingTask"]] = relationship("ProcessingTask", back_populates="knowledge_base", cascade="all, delete-orphan")
    # Relationship to DocumentChunk
    document_chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="knowledge_base", cascade="all, delete-orphan")
    # Relationship to Chat
    chats: Mapped[list["Chat"]] = relationship("Chat", secondary="chat_knowledge_bases", back_populates="knowledge_bases")


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Assuming SHA-256 hash
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationship to KnowledgeBase
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="documents")
    # Relationship to DocumentChunk
    chunks: Mapped[list["DocumentChunk"]] = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    # Relationship to ProcessingTask
    processing_tasks: Mapped[list["ProcessingTask"]] = relationship("ProcessingTask", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        # 确保在同一个知识库中，文件名是唯一的
        sqlalchemy.UniqueConstraint('knowledge_base_id', 'file_name', name='uq_knowledge_base_file_name'),
    )


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Keep the chunk text in the relational store as the lexical-retrieval source.
    # It is nullable so existing deployments can upgrade without losing data.
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False,index=True)  # Assuming SHA-256 hash

    # Relationship to Document
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    # Relationship to KnowledgeBase
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="document_chunks")
    __table_args__ = (
        sqlalchemy.Index('idx_knowledge_base_file_name', 'knowledge_base_id', 'file_name'),
    ) 


class DocumentUpload(Base, TimestampMixin):
    __tablename__ = "document_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    knowledge_base_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # Assuming SHA-256 hash
    temp_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False,server_default="pending")  # e.g., 'pending', 'processing', 'completed', 'failed'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship to KnowledgeBase
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="document_uploads")
    # Relationship to ProcessingTask
    processing_tasks: Mapped[list["ProcessingTask"]] = relationship("ProcessingTask", back_populates="document_upload", cascade="all, delete-orphan")


class ProcessingTask(Base, TimestampMixin):
    __tablename__ = "processing_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_upload_id: Mapped[int] = mapped_column(Integer, ForeignKey("document_uploads.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True)
    knowledge_base_id: Mapped[int] = mapped_column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False,server_default="pending")  # e.g., 'pending', 'processing', 'completed', 'failed'
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship to DocumentUpload
    document_upload: Mapped["DocumentUpload"] = relationship("DocumentUpload", back_populates="processing_tasks")
    # Relationship to KnowledgeBase
    knowledge_base: Mapped["KnowledgeBase"] = relationship("KnowledgeBase", back_populates="processing_tasks")
    # Relationship to Document
    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="processing_tasks")
