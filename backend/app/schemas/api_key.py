from pydantic import BaseModel, ConfigDict, Field

class APIKeyBase(BaseModel):
    name: str = Field(..., description="API Key名称")
 
class APIKeyCreate(APIKeyBase):
    pass

class APIKeyUpdate(BaseModel):
    name: str | None = Field(None, description="API Key名称")

class APIKeyResponse(BaseModel):
    id: int = Field(..., description="API Key ID")
    key: str = Field(..., validation_alias="api_key", description="API Key值")
    name: str = Field(..., description="API Key名称")
    user_id: int = Field(..., description="用户ID")
    last_used_at: str | None = Field(None, description="上次使用时间")

    model_config = ConfigDict(from_attributes=True)


class APIKeyListResponse(BaseModel):
    """列表页使用的脱敏响应；完整密钥只在创建时返回一次。"""
    id: int
    key: str
    name: str
    user_id: int
    last_used_at: str | None = None
