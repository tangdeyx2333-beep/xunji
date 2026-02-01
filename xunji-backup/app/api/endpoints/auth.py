from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.session import get_db
from app.models.sql_models import User
from app.schemas.auth import UserCreate, UserLogin, Token, UserOut
from app.core.security import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter()


# --- 1. 注册接口 ---
@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # 检查用户名是否存在
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="用户名已被注册"
        )

    print(user_in.password)
    password = get_password_hash(user_in.password)
    print(len(password))
    # 创建新用户
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=password  # ★ 加密存储
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# --- 2. 登录接口 ---
@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    # 查找用户
    user = db.query(User).filter(User.username == user_in.username).first()

    # 验证 用户是否存在 + 密码是否正确
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 生成 Token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},  # 把 user_id 塞进 token 里
        expires_delta=access_token_expires
    )

    # 返回 Token 和用户信息
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username
    }