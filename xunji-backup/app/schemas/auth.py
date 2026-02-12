from pydantic import BaseModel, EmailStr


# 注册请求体
class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None


# 登录请求体
class UserLogin(BaseModel):
    username: str
    password: str


# Token 响应体 (登录成功返回这个)
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    device_id: str | None = None


class DeviceLogin(BaseModel):
    device_id: str


class UpgradeAccount(BaseModel):
    username: str
    password: str | None = None


# 用户信息响应 (不包含密码)
class UserOut(BaseModel):
    id: str
    username: str
    email: str | None

    class Config:
        from_attributes = True
