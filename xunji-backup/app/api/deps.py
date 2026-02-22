from fastapi import Depends, HTTPException, status, Header
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.sql_models import User
from app.core.security import SECRET_KEY, ALGORITHM
import uuid


def generate_anonymous_username() -> str:
    return f"user_{uuid.uuid4().hex[:8]}"


async def get_current_user(
        db: Session = Depends(get_db),
        authorization: str = Header(None, alias="Authorization"),
        x_device_id: str = Header(None, alias="X-Device-ID")
) -> User:
    # 1. 优先尝试通过 Token 认证
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            # 优先从 user_id 字段获取
            user_id: str = payload.get("user_id")
            
            # 如果没有 user_id，尝试从 sub 获取（可能是 username，也可能是 ID，取决于历史版本）
            # 但标准 JWT 中 sub 通常是主题。我们在 auth.py 中 sub=username
            username: str = payload.get("sub")
            
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user
            
            if not user_id and username:
                # 尝试通过用户名查找
                user = db.query(User).filter(User.username == username).first()
                if user:
                    return user
                    
        except JWTError:
            pass  # Token 无效，降级处理

    # 2. 如果没有 Token 或 Token 无效，尝试通过设备 ID 认证（匿名用户）
    if x_device_id:
        # 注意：这里可能存在隐患，如果一个设备 ID 对应多个用户（如登录用户和匿名用户）
        # 应该优先找匿名用户，或者根据业务逻辑调整
        # 但通常登录用户会走上面的 Token 逻辑，走到这里说明没有 Token
        user = db.query(User).filter(User.device_id == x_device_id).first()
        if user:
            return user

    # 3. 如果都没有，创建新的匿名用户
    device_id = x_device_id or str(uuid.uuid4())
    anonymous_username = generate_anonymous_username()
    
    new_user = User(
        username=anonymous_username,
        device_id=device_id,
        hashed_password="",
        is_anonymous=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user
