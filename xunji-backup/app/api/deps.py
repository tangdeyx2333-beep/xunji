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
    if x_device_id:
        user = db.query(User).filter(User.device_id == x_device_id).first()
        if user:
            return user
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无法验证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id: str = payload.get("user_id")
            if user_id is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise credentials_exception
        return user
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
