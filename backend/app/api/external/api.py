from fastapi import APIRouter
from app.api.external import knowledge


external_router = APIRouter()

external_router.include_router(knowledge.router, prefix="/knowledge", tags=["外部API知识库"])
    
