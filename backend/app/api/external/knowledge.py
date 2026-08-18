from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db

from app.core.config import settings
from app.services.auth import get_api_key_user
from app.services.embeddig.embedding_factory import EmbeddingFactory
from app.services.vector_store.factory import VectorStoreFactory
from app.services.hybrid_retriever import HybridRetriever


router = APIRouter()

@router.get("/{knowledge_base_id}/query")
def query_knowledge_base(
    *,
    db: Session = Depends(get_db),
    knowledge_base_id: int,
    query: str,
    top_k: int = 3,
    current_user: models.User = Depends(get_api_key_user),
) -> Any:
    """
    Query a specific knowledge base using API key authentication
    """
    try:
        kb = db.query(models.KnowledgeBase).filter(
            models.KnowledgeBase.id == knowledge_base_id,
            models.KnowledgeBase.user_id == current_user.id
        ).first()
        
        if not kb:
            raise HTTPException(
                status_code=404,
                detail=f"Knowledge base {knowledge_base_id} not found",
            )
        
        embeddings = EmbeddingFactory.create()
        
        vector_store = VectorStoreFactory.create(
            store_type=settings.VECTOR_STORE_TYPE,
            collection_name=f"kb_{knowledge_base_id}",
            embeddings_function=embeddings,
        )
        
        results = HybridRetriever(
            vector_stores=[vector_store],
            db=db,
            knowledge_base_ids=[knowledge_base_id],
            final_k=top_k,
        ).invoke(query)
        
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
