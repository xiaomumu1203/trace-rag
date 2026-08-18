from contextlib import asynccontextmanager
import logging
import app.models
from app.api.v1.api import v1_router
from app.api.external.api import  external_router
from app.core.config import settings
from fastapi import FastAPI
from app.db.session import engine
from app.db.migrations import run_migrations
from app.core.minio_client import init_minio
from app.services.chat_memory import chat_memory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_minio()

    # 创建不存在的数据库表
    run_migrations()
    yield
    await chat_memory.close()
    # 关闭数据库连接
    engine.dispose()

app = FastAPI(
    title="Trace RAG API",
    description="API for Trace RAG application",
    version=settings.VERSION,
    lifespan=lifespan
)

app.include_router(v1_router, prefix="/api")
app.include_router(external_router, prefix="/external")


@app.get("/")
async def root():
    return {"message": "Welcome to TraceRAG API!"}


@app.get("/health")
async def health():
    return {"status": "Healthy"}
