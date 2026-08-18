from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeBaseBase(BaseModel):
    name: str = Field(...,description="知识库名称")
    description: str | None = Field(default=None,description="知识库描述")

class KnowledgeBaseCreate(KnowledgeBaseBase):
    pass

class KnowledgeBaseUpdate(KnowledgeBaseBase):
    pass


class DocumentBase(BaseModel):
    file_name: str = Field(...,description="文档名称")
    file_path: str = Field(...,description="文档路径")
    file_size: int = Field(...,description="文档大小")
    file_hash: str = Field(...,description="文档哈希值")
    content_type: str = Field(...,description="文档类型")

class DocumentCreate(DocumentBase):
    knowledge_base_id: int = Field(...,description="知识库ID")

class DocumentUploadBase(BaseModel):
    file_name: str = Field(...,description="文档名称")
    file_path: str = Field(...,description="文档路径")
    file_size: int = Field(...,description="文档大小")
    content_type: str = Field(...,description="文档类型")
    temp_file_path: str = Field(...,description="临时文档路径")
    status: str = Field("pending", description="文档上传状态")
    error_message: str | None = Field(default=None,description="文档上传错误信息")

class DocumentUploadCreate(DocumentUploadBase):
    knowledge_base_id: int = Field(...,description="知识库ID")

class DocumentUploadResponse(DocumentUploadBase):
    id: int = Field(...,description="文档上传ID")

    model_config = ConfigDict(from_attributes=True)

class ProcessingTaskBase(BaseModel):
    status: str = Field(...,description="处理状态")
    error_message: str | None = Field(default=None,description="处理错误信息")

class ProcessingTaskCreate(ProcessingTaskBase):
    document_id: int = Field(...,description="文档ID")
    knowledge_base_id: int = Field(...,description="知识库ID")

class ProcessingTaskResponse(ProcessingTaskBase):
    id: int = Field(...,description="处理任务ID")
    document_id: int = Field(...,description="文档ID")
    knowledge_base_id: int = Field(...,description="知识库ID")
    created_at: datetime = Field(...,description="处理任务创建时间")
    updated_at: datetime = Field(...,description="处理任务更新时间")

    model_config = ConfigDict(from_attributes=True)

class DocumentResponse(BaseModel):
    id: int = Field(...,description="文档ID")
    knowledge_base_id: int = Field(...,description="知识库ID")
    file_name: str = Field(..., description="文档名称")
    file_size: int = Field(..., description="文档大小")
    content_type: str = Field(..., description="文档类型")
    processing_tasks: List[ProcessingTaskResponse] = Field(default_factory=list,description="处理任务")
    created_at: datetime = Field(...,description="文档创建时间")
    updated_at: datetime = Field(...,description="文档更新时间")

    model_config = ConfigDict(from_attributes=True)

class KnowledgeBaseResponse(KnowledgeBaseBase):
    id : int = Field(...,description="知识库ID")
    user_id: int = Field(...,description="用户ID")
    documents: List[DocumentResponse] = Field(default_factory=list,description="知识库中的文档")
    created_at: datetime = Field(...,description="知识库创建时间")
    updated_at: datetime = Field(...,description="知识库更新时间")

    model_config = ConfigDict(from_attributes=True)


class PreviewRequest(BaseModel):
    """
    预览文档请求
    """
    document_ids: List[int] = Field(...,description="文档ID列表")
    chunk_size: int = Field(...,description="分块大小")
    chunk_overlap: int = Field(...,description="分块重叠大小")
