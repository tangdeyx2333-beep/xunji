from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class OpenClawConfigBase(BaseModel):
    display_name: str
    gateway_url: str
    session_key: str
    gateway_token: Optional[str] = None
    use_ssh: bool = False
    ssh_host: Optional[str] = None
    ssh_port: Optional[int] = 22
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_local_port: Optional[int] = 0


class OpenClawConfigCreate(OpenClawConfigBase):
    user_id: str


class OpenClawConfigUpdate(OpenClawConfigBase):
    pass


class OpenClawConfigInDB(OpenClawConfigBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class OpenClawConfig(OpenClawConfigInDB):
    pass
