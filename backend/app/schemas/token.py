
from pydantic import BaseModel, Field

class Token(BaseModel):
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field(..., description="令牌类型")

class TokenPayload(BaseModel):
    sub: str = Field(..., description="用户ID")
    exp: int = Field(..., description="过期时间")