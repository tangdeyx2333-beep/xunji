import hashlib
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import jwt

SECRET_KEY = "xunji_secret_key_change_me_please"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 365 * 10

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> Optional[str]:
    if not password:
        return None
    sha256_bin = hashlib.sha256(password.encode('utf-8')).digest()
    return pwd_context.hash(sha256_bin)


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    if not hashed_password:
        return True
    sha256_bin = hashlib.sha256(plain_password.encode('utf-8')).digest()
    print(pwd_context.hash(sha256_bin))
    return pwd_context.verify(sha256_bin, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
