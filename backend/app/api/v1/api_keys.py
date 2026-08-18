from typing import Any

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.schemas.api_key import APIKeyCreate, APIKeyListResponse, APIKeyResponse, APIKeyUpdate
from app.db.session import get_db
from app.models.user import User
from app.services import auth
from app.services.api_key import APIKeyService


router = APIRouter()

logger = logging.getLogger(__name__)
@router.get("/", response_model=list[APIKeyListResponse], tags=["获取APIKey列表"])
async def get_api_keys(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(auth.get_current_user)
)->Any:
    """
    获取APIKey列表
    """
    api_keys = APIKeyService.get_api_keys(
        db=db,
        user_id=current_user.id,
        skip=skip,
        limit=limit
    )
    return [
        {
            "id": api_key.id,
            "key": f"{api_key.api_key[:6]}...{api_key.api_key[-4:]}",
            "name": api_key.name,
            "user_id": api_key.user_id,
            "last_used_at": (
                api_key.last_used_at.isoformat() if api_key.last_used_at else None
            ),
        }
        for api_key in api_keys
    ]



@router.post("/",response_model=APIKeyResponse,tags=["创建APIKey"])
async def create_api_key(
    *,
    db: Session = Depends(get_db),
    api_key: APIKeyCreate,
    current_user: User = Depends(auth.get_current_user)
)->Any:
    """
    创建APIKey
    """
    new_api_key = APIKeyService.create_api_key(
        db = db,
        user_id = current_user.id,
        name = api_key.name
    )
    logger.info(f"API Key 创建成功，ID：{new_api_key.id}")
    return new_api_key



@router.put("/{api_key_id}/update",response_model=APIKeyResponse, tags=["更新APIKey"])
async def update_api_key(
    *,
    db: Session = Depends(get_db),
    api_key_id: int,
    api_key: APIKeyUpdate,
    current_user: User = Depends(auth.get_current_user)
)->Any:
    """
    更新APIKey
    """
    new_api_key = APIKeyService.get_api_key(db=db, api_key_id=api_key_id)
    if not new_api_key:
        raise HTTPException(
            status_code=404, 
            detail="API Key 不存在"
        )
    if new_api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="无权访问"
        )
    new_api_key = APIKeyService.update_api_key(db=db, api_key = new_api_key, update_data=api_key)
    logger.info(f"API Key 更新成功，ID：{new_api_key.id}")
    return new_api_key

@router.delete("/{api_key_id}/delete", tags=["删除APIKey"])
async def delete_api_key(
    *,
    db: Session = Depends(get_db),
    api_key_id: int,
    current_user: User = Depends(auth.get_current_user)
)->Any:
    """
    删除APIKey
    """
    delete_api_key = APIKeyService.get_api_key(db=db, api_key_id=api_key_id)
    if not delete_api_key:
        raise HTTPException(
            status_code=404, 
            detail="API Key 不存在"
        )
    if delete_api_key.user_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="无权访问"
        )
    APIKeyService.delete_api_key(db=db, api_key=delete_api_key)
    logger.info(f"API Key 删除成功，ID：{delete_api_key.id}")
    return {"status": "success"}
