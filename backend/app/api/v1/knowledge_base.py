import asyncio
import hashlib
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.session import get_db
from app.models.knowledge_base import (
    Document,
    DocumentUpload,
    KnowledgeBase,
    ProcessingTask,
)
from app.models.user import User
from app.schemas.knowledge_base import (
    DocumentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    PreviewRequest,
)
from app.services import auth
from app.services.document_processor import (
    PreviewResult,
    preview_document,
    process_document_background,
)
from app.core.config import settings
from app.core.minio_client import get_minio_client
from minio.error import MinioException
from app.services.vector_store.factory import VectorStoreFactory
from app.services.embeddig.embedding_factory import EmbeddingFactory
from app.services.hybrid_retriever import HybridRetriever

router = APIRouter()

logger = logging.getLogger(__name__)


class TestRetrievalRequest(BaseModel):
    """测试检索请求"""
    query: str
    kb_id: int
    top_k: int


@router.post("", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    *,
    db: Session = Depends(get_db),
    kb_in: KnowledgeBaseCreate,
    current_user: User = Depends(auth.get_current_user),
) -> Any:
    """
    创建新知识库
    """
    kb = KnowledgeBase(
        name=kb_in.name,
        description=kb_in.description,
        user_id=current_user.id
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    logger.info(f"知识库创建成功: {kb.name}，用户: {current_user.id}")
    return kb


@router.get("", response_model=List[KnowledgeBaseResponse])
def get_knowledge_bases(
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user),
    skip: int = 0,
    limit: int = 100
) -> Any:
    """
    获取知识库列表
    """
    knowledge_bases = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return knowledge_bases


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    *,
    db: Session = Depends(get_db),
    kb_id: int,
    current_user: User = Depends(auth.get_current_user)
) -> Any:
    """
    根据 ID 获取知识库
    """
    kb = (
        db.query(KnowledgeBase)
        .options(
            joinedload(KnowledgeBase.documents)
            .joinedload(Document.processing_tasks)
        )
        .filter(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
        .first()
    )

    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    return kb


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    *,
    db: Session = Depends(get_db),
    kb_id: int,
    kb_in: KnowledgeBaseUpdate,
    current_user: User = Depends(auth.get_current_user)
) -> Any:
    """
    更新知识库
    """
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user.id
    ).first()

    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    for field, value in kb_in.dict(exclude_unset=True).items():
        setattr(kb, field, value)

    db.add(kb)
    db.commit()
    db.refresh(kb)
    logger.info(f"知识库更新成功: {kb.name}，用户: {current_user.id}")
    return kb


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    *,
    db: Session = Depends(get_db),
    kb_id: int,
    current_user: User = Depends(auth.get_current_user)
) -> Any:
    """
    删除知识库及其所有关联资源
    """
    kb = (
        db.query(KnowledgeBase)
        .filter(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
        .first()
    )
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    try:
        # 初始化服务
        minio_client = get_minio_client()
        embeddings = EmbeddingFactory.create()

        vector_store = VectorStoreFactory.create(
            store_type=settings.VECTOR_STORE_TYPE,
            collection_name=f"kb_{kb_id}",
            embeddings_function=embeddings,
        )

        # 先清理外部资源
        cleanup_errors = []

        # 1. 清理 MinIO 文件
        try:
            # 删除所有以 kb_{kb_id}/ 为前缀的对象
            objects = minio_client.list_objects(settings.MINIO_BUCKET_NAME, prefix=f"kb_{kb_id}/")
            for obj in objects:
                minio_client.remove_object(settings.MINIO_BUCKET_NAME, str(obj.object_name))
            logger.info(f"知识库 {kb_id} 的 MinIO 文件清理完成")
        except MinioException as e:
            cleanup_errors.append(f"清理 MinIO 文件失败: {str(e)}")
            logger.error(f"知识库 {kb_id} 的 MinIO 清理出错: {str(e)}")

        # 2. 清理向量存储
        try:
            vector_store.delete_collection()
            logger.info(f"知识库 {kb_id} 的向量存储清理完成")
        except Exception as e:
            cleanup_errors.append(f"清理向量存储失败: {str(e)}")
            logger.error(f"知识库 {kb_id} 的向量存储清理出错: {str(e)}")

        # 最后，在单个事务中删除数据库记录
        db.delete(kb)
        db.commit()

        # 在响应中报告任何清理错误
        if cleanup_errors:
            return {
                "message": "知识库已删除，但有清理警告",
                "warnings": cleanup_errors
            }

        return {"message": "知识库及其所有关联资源已成功删除"}
    except Exception as e:
        db.rollback()
        logger.error(f"删除知识库 {kb_id} 失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除知识库失败: {str(e)}")


# 批量上传文档
@router.post("/{kb_id}/documents/upload")
async def upload_kb_documents(
    kb_id: int,
    files: List[UploadFile],
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    """
    上传多个文档到 MinIO
    """
    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user.id
    ).first()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    results = []
    for file in files:
        # 1. 计算文件 hash
        file_content = await file.read()
        file_hash = hashlib.sha256(file_content).hexdigest()

        # 2. 检查是否存在完全相同的文件（名称和 hash 都相同）
        existing_document = db.query(Document).filter(
            Document.file_name == file.filename,
            Document.file_hash == file_hash,
            Document.knowledge_base_id == kb_id
        ).first()

        if existing_document:
            # 完全相同的文件，直接返回
            results.append({
                "document_id": existing_document.id,
                "file_name": existing_document.file_name,
                "status": "exists",
                "message": "文件已存在且已处理完成",
                "skip_processing": True
            })
            continue

        # 3. 上传到临时目录
        temp_path = f"kb_{kb_id}/temp/{file.filename}"
        await file.seek(0)
        try:
            minio_client = get_minio_client()
            file_size = len(file_content)  # 使用之前读取的文件内容长度
            minio_client.put_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=temp_path,
                data=file.file,
                length=file_size,  # 指定文件大小
                content_type=file.content_type or "application/octet-stream"
            )
        except MinioException as e:
            logger.error(f"上传文件到 MinIO 失败: {str(e)}")
            raise HTTPException(status_code=500, detail="上传文件失败")

        # 4. 创建上传记录
        upload = DocumentUpload(
            knowledge_base_id=kb_id,
            file_name=file.filename,
            file_path=temp_path,  # 临时路径占位，处理完成后更新为永久路径
            file_hash=file_hash,
            file_size=len(file_content),
            content_type=file.content_type,
            temp_file_path=temp_path
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)

        results.append({
            "upload_id": upload.id,
            "file_name": file.filename,
            "temp_path": temp_path,
            "status": "pending",
            "skip_processing": False
        })

    return results


@router.post("/{kb_id}/documents/preview")
async def preview_kb_documents(
    kb_id: int,
    preview_request: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
) -> Dict[int, PreviewResult]:
    """
    预览多个文档的分块
    """
    results = {}
    for doc_id in preview_request.document_ids:
        document = db.query(Document).join(KnowledgeBase).filter(
            Document.id == doc_id,
            Document.knowledge_base_id == kb_id,
            KnowledgeBase.user_id == current_user.id
        ).first()

        if document:
            file_path = document.file_path
        else:
            upload = db.query(DocumentUpload).join(KnowledgeBase).filter(
                DocumentUpload.id == doc_id,
                DocumentUpload.knowledge_base_id == kb_id,
                KnowledgeBase.user_id == current_user.id
            ).first()

            if not upload:
                raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")

            file_path = upload.temp_file_path

        preview = await preview_document(
            file_path,
            chunk_size=preview_request.chunk_size,
            chunk_overlap=preview_request.chunk_overlap
        )
        results[doc_id] = preview

    return results


@router.post("/{kb_id}/documents/process")
async def process_kb_documents(
    kb_id: int,
    upload_results: List[dict],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    """
    异步处理多个文档
    """
    start_time = time.time()

    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user.id
    ).first()

    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    task_info = []
    upload_ids = []

    for result in upload_results:
        if result.get("skip_processing"):
            continue
        upload_ids.append(result["upload_id"])

    if not upload_ids:
        return {"tasks": []}

    uploads = db.query(DocumentUpload).filter(
        DocumentUpload.id.in_(upload_ids),
        DocumentUpload.knowledge_base_id == kb_id
    ).all()
    uploads_dict = {upload.id: upload for upload in uploads}
    if len(uploads_dict) != len(set(upload_ids)):
        raise HTTPException(status_code=400, detail="一个或多个上传 ID 无效")

    all_tasks = []
    for upload_id in upload_ids:
        upload = uploads_dict.get(upload_id)
        if not upload:
            continue

        task = ProcessingTask(
            document_upload_id=upload_id,
            knowledge_base_id=kb_id,
            status="pending"
        )
        all_tasks.append(task)

    db.add_all(all_tasks)
    db.commit()

    for task in all_tasks:
        db.refresh(task)

    task_data = []
    for i, upload_id in enumerate(upload_ids):
        if i < len(all_tasks):
            task = all_tasks[i]
            upload = uploads_dict.get(upload_id)

            task_info.append({
                "upload_id": upload_id,
                "task_id": task.id
            })

            if upload:
                task_data.append({
                    "task_id": task.id,
                    "upload_id": upload_id,
                    "temp_path": upload.temp_file_path,
                    "file_name": upload.file_name
                })

    background_tasks.add_task(
        add_processing_tasks_to_queue,
        task_data,
        kb_id
    )

    return {"tasks": task_info}


async def add_processing_tasks_to_queue(task_data, kb_id):
    """辅助函数：将文档处理任务加入队列，不阻塞主响应"""
    def process_batch() -> None:
        # Process one file at a time in a worker thread. This keeps model memory
        # bounded while leaving the event loop free for status polling requests.
        for data in task_data:
            process_document_background(
                data["temp_path"],
                data["file_name"],
                kb_id,
                data["task_id"],
                None,
            )

    if task_data:
        await asyncio.to_thread(process_batch)
    logger.info(f"已将 {len(task_data)} 个文档处理任务加入队列")


@router.post("/cleanup")
async def cleanup_temp_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    """
    清理过期的临时文件
    """
    expired_time = datetime.utcnow() - timedelta(hours=24)
    expired_uploads = db.query(DocumentUpload).filter(
        DocumentUpload.created_at < expired_time
    ).all()

    minio_client = get_minio_client()
    for upload in expired_uploads:
        try:
            minio_client.remove_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=upload.temp_file_path
            )
        except MinioException as e:
            logger.error(f"删除临时文件 {upload.temp_file_path} 失败: {str(e)}")

        db.delete(upload)

    db.commit()

    return {"message": f"已清理 {len(expired_uploads)} 个过期上传"}


@router.get("/{kb_id}/documents/tasks")
async def get_processing_tasks(
    kb_id: int,
    task_ids: str = Query(..., description="逗号分隔的任务 ID 列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
):
    """
    获取多个处理任务的状态
    """
    task_id_list = [int(task_id.strip()) for task_id in task_ids.split(",") if task_id.strip()]

    kb = db.query(KnowledgeBase).filter(
        KnowledgeBase.id == kb_id,
        KnowledgeBase.user_id == current_user.id
    ).first()

    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    tasks = (
        db.query(ProcessingTask)
        .options(
            selectinload(ProcessingTask.document_upload)
        )
        .filter(
            ProcessingTask.id.in_(task_id_list),
            ProcessingTask.knowledge_base_id == kb_id,
        )
        .all()
    )

    return {
        task.id: {
            "document_id": task.document_id,
            "status": task.status,
            "error_message": task.error_message,
            "upload_id": task.document_upload_id,
            "file_name": task.document_upload.file_name if task.document_upload else None
        }
        for task in tasks
    }


@router.get("/{kb_id}/documents/{doc_id}", response_model=DocumentResponse)
async def get_document(
    *,
    db: Session = Depends(get_db),
    kb_id: int,
    doc_id: int,
    current_user: User = Depends(auth.get_current_user)
) -> Any:
    """
    根据 ID 获取文档详情
    """
    document = (
        db.query(Document)
        .join(KnowledgeBase)
        .filter(
            Document.id == doc_id,
            Document.knowledge_base_id == kb_id,
            KnowledgeBase.user_id == current_user.id
        )
        .first()
    )

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    return document


@router.post("/test-retrieval")
async def test_retrieval(
    request: TestRetrievalRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(auth.get_current_user)
) -> Any:
    """
    测试指定知识库对查询的检索效果
    """
    try:
        kb = db.query(KnowledgeBase).filter(
            KnowledgeBase.id == request.kb_id,
            KnowledgeBase.user_id == current_user.id
        ).first()

        if not kb:
            raise HTTPException(
                status_code=404,
                detail=f"知识库 {request.kb_id} 不存在",
            )

        embeddings = EmbeddingFactory.create()

        vector_store = VectorStoreFactory.create(
            store_type=settings.VECTOR_STORE_TYPE,
            collection_name=f"kb_{request.kb_id}",
            embeddings_function=embeddings,
        )

        results = HybridRetriever(
            vector_stores=[vector_store],
            db=db,
            knowledge_base_ids=[request.kb_id],
            final_k=request.top_k,
        ).invoke(request.query)

        response = []
        for doc in results:
            response.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(doc.metadata.get("rrf_score", 0.0)),
                "dense_rank": doc.metadata.get("dense_rank"),
                "bm25_rank": doc.metadata.get("bm25_rank"),
            })

        return {"results": response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
