"""TraceRAG MCP Server —— 把知识库检索能力暴露为标准 MCP 工具。

三种启动方式：

1) 手动（stdio，用于调试）：
       python mcp_server.py

2) Docker 容器内：
       docker compose exec backend python mcp_server.py

3) 被 MCP 客户端拉起（推荐，Claude Desktop / Cursor / Cline 都支持）：
   客户端配置里写 command + args 即可，本进程由客户端负责启动与关闭。

stdio 传输下 stdout 是协议通道，任何 print() 都会破坏协议，
所以本模块所有日志一律走 stderr，且禁止在工具函数里 print。
"""

from __future__ import annotations

import json
import logging
import os
import sys

# 必须在导入 chromadb / transformers 之前设置，否则它们会往 stdout 写东西
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from mcp.server.fastmcp import FastMCP

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.knowledge_base import DocumentChunk, KnowledgeBase
from app.services.embeddig.embedding_factory import EmbeddingFactory
from app.services.hybrid_retriever import HybridRetriever
from app.services.vector_store.factory import VectorStoreFactory

# stdio 模式下 stdout 归协议所有，日志只能走 stderr
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("trace-rag-mcp")

mcp = FastMCP("trace-rag")


# --------------------------------------------------------------------------
# 内部实现：把业务逻辑和 MCP 装饰器分开，方便 tools / resources 复用
# --------------------------------------------------------------------------

def _list_knowledge_bases(user_id: int) -> list[dict]:
    with SessionLocal() as db:
        rows = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.id)
            .all()
        )
        return [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
                "document_count": len(row.documents),
            }
            for row in rows
        ]


def _build_vector_store(kb_id: int):
    return VectorStoreFactory.create(
        store_type=settings.VECTOR_STORE_TYPE,
        collection_name=f"kb_{kb_id}",
        embeddings_function=EmbeddingFactory.create(),
    )


def _search(query: str, kb_id: int, top_k: int, user_id: int) -> list[dict]:
    with SessionLocal() as db:
        kb = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user_id)
            .first()
        )
        if kb is None:
            return [{"error": f"知识库 {kb_id} 不存在，或不属于用户 {user_id}"}]

        retriever = HybridRetriever(
            vector_stores=[_build_vector_store(kb_id)],
            db=db,
            knowledge_base_ids=[kb_id],
            candidate_k=20,
            final_k=max(1, min(top_k, 20)),
            rrf_k=60,
        )
        documents = retriever.invoke(query)

        results: list[dict] = []
        for rank, doc in enumerate(documents, start=1):
            metadata = doc.metadata or {}
            results.append(
                {
                    "rank": rank,
                    "content": doc.page_content,
                    "chunk_id": metadata.get("chunk_id"),
                    # dense 路径写入向量库时只有 source，BM25 路径才补 file_name，
                    # 所以这里要按顺序回退，否则引用会显示不出文件名。
                    "file_name": metadata.get("file_name") or metadata.get("source"),
                    "knowledge_base": kb.name,
                    "rrf_score": metadata.get("rrf_score"),
                    "dense_rank": metadata.get("dense_rank"),
                    "bm25_rank": metadata.get("bm25_rank"),
                }
            )
        return results


# --------------------------------------------------------------------------
# MCP tools
# --------------------------------------------------------------------------

@mcp.tool()
def list_knowledge_bases(user_id: int = 1) -> list[dict]:
    """列出指定用户的知识库，返回 id、名称、描述与文档数量。

    先用这个工具确认有哪些知识库可选，再用 search_knowledge_base 检索。

    Args:
        user_id: 知识库所属的用户 ID，默认 1。
    """
    try:
        return _list_knowledge_bases(user_id)
    except Exception as exc:  # noqa: BLE001 - 工具层不抛异常，返回可读错误
        logger.exception("list_knowledge_bases 失败")
        return [{"error": f"查询知识库失败: {exc}"}]


@mcp.tool()
def search_knowledge_base(
    query: str,
    kb_id: int,
    top_k: int = 3,
    user_id: int = 1,
) -> list[dict]:
    """在指定知识库中做混合检索（向量 + 中文 BM25，RRF 融合），返回带来源的片段。

    检索策略固定为 hybrid：向量检索负责语义相近但用词不同的问题，
    jieba 分词 BM25 负责型号、参数、专有名词这类字面召回。
    返回的每一条都带 chunk_id 与 file_name，可用于引用溯源。

    Args:
        query: 用户的自然语言问题。
        kb_id: 目标知识库 ID，可从 list_knowledge_bases 获取。
        top_k: 返回条数，1-20，默认 3。
        user_id: 校验知识库归属，默认 1。
    """
    try:
        return _search(query=query, kb_id=kb_id, top_k=top_k, user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("search_knowledge_base 失败")
        return [{"error": f"检索失败: {exc}"}]


@mcp.tool()
def get_chunk_detail(chunk_id: str) -> dict:
    """按 chunk_id 取回片段的完整原文与来源信息，用于展开上一轮检索命中的引用。

    Args:
        chunk_id: 检索结果里的 chunk_id（64 位十六进制字符串）。
    """
    try:
        with SessionLocal() as db:
            row = db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
            if row is None:
                return {"error": f"chunk {chunk_id} 不存在"}
            return {
                "chunk_id": row.id,
                "file_name": row.file_name,
                "knowledge_base_id": row.knowledge_base_id,
                "document_id": row.document_id,
                "content": row.content,
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_chunk_detail 失败")
        return {"error": f"读取片段失败: {exc}"}


# --------------------------------------------------------------------------
# MCP resources（只读数据，和 tools 的主动调用互补）
# --------------------------------------------------------------------------

@mcp.resource("trace-rag://knowledge-bases/{user_id}")
def knowledge_bases_resource(user_id: str) -> str:
    """以只读资源的形式暴露知识库列表，客户端可直接挂载到上下文。"""
    try:
        return json.dumps(_list_knowledge_bases(int(user_id)), ensure_ascii=False, indent=2)
    except Exception as exc:  # noqa: BLE001
        logger.exception("knowledge_bases_resource 失败")
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


if __name__ == "__main__":
    logger.info(
        "启动 TraceRAG MCP Server (stdio) | vector_store=%s | tools: "
        "list_knowledge_bases / search_knowledge_base / get_chunk_detail",
        settings.VECTOR_STORE_TYPE,
    )
    mcp.run(transport="stdio")