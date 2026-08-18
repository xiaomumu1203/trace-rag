from datetime import timedelta
from typing import Any
from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.schemas.user import UserResponse,UserCreate

from app.schemas.token import Token
from app.db.session import get_db
from app.services import auth
from app.models.user import User


router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register(*, db: Session = Depends(get_db), user: UserCreate) -> Any:
    """
    注册新用户
    """
    try:
        existing_user = db.query(User).filter(User.username == user.username).first()
        if existing_user:
            raise HTTPException(
                status_code=400, 
                detail="用户名已存在"
            )

        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            raise HTTPException(
                status_code=400, 
                detail="邮箱已存在"
            )
        # 创建新用户
        new_user = User(
            username=user.username,
            email=user.email, 
            password=auth.get_password_hash(user.password)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user 
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail="注册失败"
        )

    
@router.post("/login",response_model=Token)
async def login(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends())->Any:
    """
    OAuth2 兼容的 token 登录接口，获取访问令牌用于后续请求的身份验证。
    """
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=401, 
            detail="用户名或密码错误",
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}
