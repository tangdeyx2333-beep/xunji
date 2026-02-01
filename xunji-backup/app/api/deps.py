from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.sql_models import User
from app.core.security import SECRET_KEY, ALGORITHM

# 1. 定义 OAuth2 模式
# tokenUrl 指向你的登录接口路由，这样 Swagger UI 上会出现一把锁，可以输入账号密码
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# 2. 核心依赖：获取当前登录用户
async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # A. 解析 Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")  # 我们在 login 生成 token 时放了 user_id

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # B. 查数据库确认用户存在
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user