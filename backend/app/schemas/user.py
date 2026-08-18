from pydantic import BaseModel, ConfigDict, Field, EmailStr


class UserBase(BaseModel):
    username: str = Field(..., description="用户名")
    email: EmailStr = Field(..., description="邮箱")

class UserCreate(UserBase):
    password: str = Field(..., description="密码")

class UserUpdate(BaseModel):
    username: str | None = Field(None, description="用户名")
    email: EmailStr | None = Field(None, description="邮箱")
    password: str | None = Field(None, description="密码")

class UserResponse(UserBase):
    id: int = Field(..., description="用户ID")

    model_config = ConfigDict(from_attributes=True)

if __name__ == "__main__":
    print(UserResponse.model_config)