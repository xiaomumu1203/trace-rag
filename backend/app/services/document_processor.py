from io import BytesIO
import hashlib, logging

import os
import tempfile
import traceback
from typing import Any, Dict, List, Optional
from fastapi import Depends, UploadFile
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from minio.commonconfig import CopySource
from minio.error import MinioException
from pydantic import BaseModel, Field

from langchain_core.documents import Document as LangchainDocument
from sqlalchemy.orm import Session
from app.services.embeddig.embedding_factory import EmbeddingFactory
from app.services.vector_store.factory import VectorStoreFactory
from app.core.config import settings
from app.services.chunk_record import ChunkRecord
from app.core.minio_client import get_minio_client
from app.db.session import SessionLocal, get_db
from app.models.knowledge_base import Document, DocumentChunk, ProcessingTask


class UploadResult(BaseModel):
    file_path: str
    file_name: str
    file_size: int
    content_type: str
    file_hash: str

class TextChunk(BaseModel):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)

class PreviewResult(BaseModel):
    chunks: List[TextChunk]
    total_chunks: int



async def process_document(
        file_path: str, 
        kb_id: int, 
        file_name: str, 
        document_id: int,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
) -> None:
    """
    处理文档，将其拆分为块并存储在数据库中。
    """

    logger = logging.getLogger(__name__)

    try:
        preview_result = await preview_document(file_path, chunk_size, chunk_overlap)

        #初始化嵌入模型
        logger.info("初始化嵌入模型中...")
        embeddings = EmbeddingFactory.create()

        logger.info("初始化向量库...")
        vector_store = VectorStoreFactory.create(
            store_type=settings.VECTOR_STORE_TYPE,
            collection_name=f"kb_{kb_id}",
            embeddings_function=embeddings
        )

        #初始化块记录管理器
        logger.info("初始化块记录管理器...")
        chunk_manager = ChunkRecord(kb_id)

        #获取当前文件的所有块哈希值
        existing_hashes = chunk_manager.list_chunks(file_name)

        #准备新块数据
        new_chunks = []
        current_hashes = set()
        documents_to_update = []

        for chunk in preview_result.chunks:
            chunk_hash = hashlib.sha256(
                (chunk.content + str(chunk.metadata)).encode()
            ).hexdigest()
            current_hashes.add(chunk_hash)

            if chunk_hash in existing_hashes:
                continue  # 跳过已经存在的块

            #创建专门的chunk_id
            chunk_id = hashlib.sha256(
                f"{kb_id}:{file_name}:{chunk_hash}".encode()
            ).hexdigest()

            metadata = {
                **chunk.metadata,
                "chunk_id": chunk_id,
                "file_name": file_name,
                "kb_id": kb_id,
                "document_id": document_id
            }
            
            new_chunks.append({
                "id": chunk_id,
                "kb_id": kb_id,
                "document_id": document_id,
                "file_name": file_name,
                "content": chunk.content,
                "metadata": metadata,
                "hash": chunk_hash
            })

            doc = LangchainDocument(
                page_content=chunk.content,
                metadata=metadata
            )
            documents_to_update.append(doc)

        if new_chunks:
            logger.info(f"添加 {len(new_chunks)} 个块")
            chunk_manager.add_chunk(new_chunks)
            vector_store.add_documents(documents_to_update)

        chunks_to_delete = chunk_manager.get_deleted_chunks(current_hashes, file_name)
        if chunks_to_delete:
            logger.info(f"删除 {len(chunks_to_delete)} 个块")
            chunk_manager.delete_chunks(chunks_to_delete)
            vector_store.delete(chunks_to_delete)

        logger.info("文档处理完成")

    except Exception as e:
        logger.info(f"文档处理出错: {str(e)}")
        raise


async def upload_document(file: UploadFile, kb_id: int) -> UploadResult:
    """上传文档到minio中"""
    content = await file.read()
    file_size = len(content)
    
    file_hash = hashlib.sha256(content).hexdigest()
    
    file_name = "".join(
        c for c in (file.filename or "")
        if c.isalnum() or c in ("-", "_", ".")
    ).strip()    

    object_path = f"kb_{kb_id}/{file_name}"
        
    content_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".md": "text/markdown",
        ".txt": "text/plain"
    }
    
    _, ext = os.path.splitext(file_name)
    content_type = content_types.get(ext.lower(), "application/octet-stream")
    
    # 上传到MinIO
    minio_client = get_minio_client()
    try:
        minio_client.put_object(
            bucket_name=settings.MINIO_BUCKET_NAME,
            object_name=object_path,
            data=BytesIO(content),
            length=file_size,
            content_type=content_type
        )
    except Exception as e:
        logging.error(f"上传到MinIO失败: {str(e)}")
        raise
        
    return UploadResult(
        file_path=object_path,
        file_name=file_name,
        file_size=file_size,
        content_type=content_type,
        file_hash=file_hash
    )

async def preview_document(file_path: str,chunk_size: int = 1000, chunk_overlap: int = 200)->PreviewResult:

    #获得一个minio
    minio_client = get_minio_client()
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()

    #下载临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
        minio_client.fget_object(
            bucket_name=settings.MINIO_BUCKET_NAME,
            object_name=file_path,
            file_path=temp_file.name
        )
        temp_path = temp_file.name

    try:
        if ext == ".pdf":
            loader = PyPDFLoader(temp_path)
        elif ext == ".docx":
            loader = Docx2txtLoader(temp_path)
        elif ext == ".md":
            loader = UnstructuredMarkdownLoader(temp_path)
        else:  
            loader = TextLoader(temp_path)    

        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        chunks = text_splitter.split_documents(documents)

        preview_chunks = [
            TextChunk(
                content=chunk.page_content,
                metadata=chunk.metadata
            )
            for chunk in chunks
        ]        

        return PreviewResult(
                chunks=preview_chunks,
                total_chunks=len(chunks)
            )
    
    finally:
        os.unlink(temp_path)


def process_document_background(
    temp_path: str,
    file_name: str,
    kb_id: int,
    task_id: int,
    db: Optional[Session] = Depends(get_db),
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> None:
    
    logger = logging.getLogger(__name__)
    logger.info(f"开始后台处理任务 {task_id}，文件: {file_name}")

    if db is None:
        db = SessionLocal()
        should_close_db = True
    else:
        should_close_db = False
    
    task = db.query(ProcessingTask).get(task_id)
    if not task:
        logger.error(f"任务 {task_id} 不存在")
        return

    minio_client = None  # 提前声明，供异常清理时使用
    try:
        logger.info(f"任务 {task_id}: 正在将状态更新为处理中")
        task.status = "processing"
        db.commit()
        
        # 1. 从临时目录下载文件
        minio_client = get_minio_client()

        try:
            local_temp_path = f"/tmp/temp_{task_id}_{file_name}"  # 使用系统临时目录
            logger.info(f"任务 {task_id}: 正在从 MinIO 下载文件: {temp_path} 到 {local_temp_path}")
            minio_client.fget_object(
                bucket_name=settings.MINIO_BUCKET_NAME,
                object_name=temp_path,
                file_path=local_temp_path
            )
            logger.info(f"任务 {task_id}: 文件下载成功")
        except MinioException as e:
            error_msg = f"下载临时文件失败: {str(e)}"
            logger.error(f"任务 {task_id}: {error_msg}")
            raise Exception(error_msg)
        
        try:
            # 2. 加载和分块文档
            _, ext = os.path.splitext(file_name)
            ext = ext.lower()
            
            logger.info(f"任务 {task_id}: 正在加载扩展名为 {ext} 的文档")
            # 选择合适的加载器
            if ext == ".pdf":
                loader = PyPDFLoader(local_temp_path)
            elif ext == ".docx":
                loader = Docx2txtLoader(local_temp_path)
            elif ext == ".md":
                loader = UnstructuredMarkdownLoader(local_temp_path)
            else:  # 默认使用文本加载器
                loader = TextLoader(local_temp_path)
            
            logger.info(f"任务 {task_id}: 正在加载文档内容")
            documents = loader.load()
            logger.info(f"任务 {task_id}: 文档加载成功")
            
            logger.info(f"任务 {task_id}: 正在将文档拆分为块")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            chunks = text_splitter.split_documents(documents)
            logger.info(f"任务 {task_id}: 文档已拆分为 {len(chunks)} 个块")
            
            # 3. 创建向量存储
            logger.info(f"任务 {task_id}: 正在初始化向量存储")
            embeddings = EmbeddingFactory.create()
            
            vector_store = VectorStoreFactory.create(
                store_type=settings.VECTOR_STORE_TYPE,
                collection_name=f"kb_{kb_id}",
                embeddings_function=embeddings,
            )
            
            # 4. 将临时文件移动到永久目录
            permanent_path = f"kb_{kb_id}/{file_name}"
            try:
                logger.info(f"任务 {task_id}: 正在将文件移动到永久存储")
                # 复制到永久目录
                source = CopySource(settings.MINIO_BUCKET_NAME, temp_path)
                minio_client.copy_object(
                    bucket_name=settings.MINIO_BUCKET_NAME,
                    object_name=permanent_path,
                    source=source
                )
                logger.info(f"任务 {task_id}: 文件已移动到永久存储")
                
                # 删除临时文件
                logger.info(f"任务 {task_id}: 正在从 MinIO 删除临时文件")
                minio_client.remove_object(
                    bucket_name=settings.MINIO_BUCKET_NAME,
                    object_name=temp_path
                )
                logger.info(f"任务 {task_id}: 临时文件已删除")
            except MinioException as e:
                error_msg = f"移动文件到永久存储失败: {str(e)}"
                logger.error(f"任务 {task_id}: {error_msg}")
                raise Exception(error_msg)
            
            # 5. 创建文档记录
            logger.info(f"任务 {task_id}: 正在创建文档记录")
            document = Document(
                file_name=file_name,
                file_path=permanent_path,
                file_hash=task.document_upload.file_hash,
                file_size=task.document_upload.file_size,
                content_type=task.document_upload.content_type,
                knowledge_base_id=kb_id
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            logger.info(f"任务 {task_id}: 文档记录已创建，ID: {document.id}")
            
            # 6. 存储文档块
            logger.info(f"任务 {task_id}: 正在存储文档块")
            for i, chunk in enumerate(chunks):
                # 为每个 chunk 生成唯一的 ID
                chunk_id = hashlib.sha256(
                    f"{kb_id}:{file_name}:{chunk.page_content}".encode()
                ).hexdigest()

                chunk.metadata["source"] = file_name
                chunk.metadata["kb_id"] = kb_id
                chunk.metadata["document_id"] = document.id
                chunk.metadata["chunk_id"] = chunk_id
                
                doc_chunk = DocumentChunk(
                    id=chunk_id,  # 添加 ID 字段
                    document_id=document.id,
                    knowledge_base_id=kb_id,
                    file_name=file_name,
                    content=chunk.page_content,
                    chunk_metadata={
                        "page_content": chunk.page_content,
                        **chunk.metadata
                    },
                    hash=hashlib.sha256(
                        (chunk.page_content + str(chunk.metadata)).encode()
                    ).hexdigest()
                )
                db.add(doc_chunk)
                if i > 0 and i % 100 == 0:
                    logger.info(f"任务 {task_id}: 已存储 {i} 个块")
                    db.commit()  # 每 100 条提交一次，避免事务太大
            
            # 7. 添加到向量存储
            logger.info(f"任务 {task_id}: 正在将块添加到向量存储")
            vector_store.add_documents(chunks)
            # 移除 persist() 调用，因为新版本不需要
            logger.info(f"任务 {task_id}: 块已添加到向量存储")
            
            # 8. 更新任务状态
            logger.info(f"任务 {task_id}: 正在将任务状态更新为已完成")
            task.status = "completed"
            task.document_id = document.id  # 更新为新创建的文档ID
            
            # 9. 更新上传记录状态
            upload = task.document_upload  # 直接通过关系获取
            if upload:
                logger.info(f"任务 {task_id}: 正在将上传记录状态更新为已完成")
                upload.status = "completed"
            
            db.commit()
            logger.info(f"任务 {task_id}: 处理成功完成")
            
        finally:
            # 清理本地临时文件
            try:
                if os.path.exists(local_temp_path):
                    logger.info(f"任务 {task_id}: 清理本地临时文件")
                    os.remove(local_temp_path)
                    logger.info(f"任务 {task_id}: 本地临时文件已被清除")
            except Exception as e:
                logger.warning(f"任务 {task_id}: 清除本地临时文件失败: {str(e)}")
        
    except Exception as e:
        logger.error(f"任务 {task_id}: 处理文档出错: {str(e)}")
        logger.error(f"任务 {task_id}: 堆栈跟踪: {traceback.format_exc()}")
        task.status = "failed"
        task.error_message = str(e)
        db.commit()
        
        # 清理临时文件
        try:
            if minio_client is not None:
                logger.info(f"任务 {task_id}: 出错后清理临时文件")
                minio_client.remove_object(
                    bucket_name=settings.MINIO_BUCKET_NAME,
                    object_name=temp_path
                )
                logger.info(f"任务 {task_id}: 出错后清理临时文件")
        except:
            logger.warning(f"任务 {task_id}: 清理失败")
    finally:
        if should_close_db and db:
            db.close()
