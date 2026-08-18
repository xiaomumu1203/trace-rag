import logging
from minio import Minio
from app.core.config import settings


logger = logging.getLogger(__name__)

def get_minio_client() -> Minio:
    """
    获得一个Minio客户端
    """
    logger.info("立刻创建Minio客户端")
    
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=False
    )


def init_minio():
    """
    初始化 MinIO：如果存储桶不存在，则创建存储桶。
    """
    client = get_minio_client()
    logger.info(f"检查{settings.MINIO_BUCKET_NAME}是否存在.")
    if not client.bucket_exists(settings.MINIO_BUCKET_NAME):
        logger.info(f"{settings.MINIO_BUCKET_NAME}不存在，创建存储桶")
        client.make_bucket(settings.MINIO_BUCKET_NAME)
    else:
        logger.info(f"{settings.MINIO_BUCKET_NAME}已存在")