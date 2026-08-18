from fastapi import APIRouter
from app.api.v1 import api_keys, auth, chat, knowledge_base

v1_router = APIRouter()

v1_router.include_router(auth.router, prefix="/auth", tags=["用户管理"])
v1_router.include_router(knowledge_base.router,prefix="/knowledge-base",tags=["知识库"])
v1_router.include_router(chat.router,prefix="/chat",tags=["聊天"])
v1_router.include_router(api_keys.router,prefix="/api-keys",tags=["api-keys"])
