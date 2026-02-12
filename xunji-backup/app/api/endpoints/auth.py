from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from datetime import timedelta

from app.db.session import get_db
from app.models.sql_models import User
from app.schemas.auth import UserCreate, UserLogin, Token, UserOut, DeviceLogin, UpgradeAccount
from app.core.security import get_password_hash, verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
import uuid

router = APIRouter()


@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_in.username).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="用户名已被注册"
        )
    password = get_password_hash(user_in.password) or ""
    new_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=password,
        is_anonymous=False
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=Token)
def login(user_in: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == user_in.username).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "device_id": user.device_id},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "device_id": user.device_id
    }


@router.post("/anonymous-login", response_model=Token)
def anonymous_login(payload: DeviceLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.device_id == payload.device_id).first()
    if not user:
        username = f"user_{uuid.uuid4().hex[:8]}"
        user = User(
            username=username,
            device_id=payload.device_id,
            hashed_password="",
            is_anonymous=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "device_id": user.device_id},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "device_id": user.device_id
    }


@router.post("/upgrade-account", response_model=Token)
def upgrade_account(
    payload: UpgradeAccount,
    db: Session = Depends(get_db),
    x_device_id: str = Header(None, alias="X-Device-ID")
):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="缺少设备标识")
    user = db.query(User).filter(User.device_id == x_device_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="未找到当前用户")

    existing = db.query(User).filter(User.username == payload.username).first()
    if existing and existing.id != user.id:
        raise HTTPException(status_code=400, detail="用户名已被注册")

    user.username = payload.username
    user.hashed_password = get_password_hash(payload.password) or ""
    user.is_anonymous = False
    db.commit()
    db.refresh(user)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id, "device_id": user.device_id},
        expires_delta=access_token_expires
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username,
        "device_id": user.device_id
    }
