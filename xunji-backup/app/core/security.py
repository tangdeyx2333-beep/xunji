# app/core/security.py
import hashlib  # ★ 必须导入这个
from datetime import datetime, timedelta
from typing import Optional
from passlib.context import CryptContext
from jose import jwt

# 配置
SECRET_KEY = "xunji_secret_key_change_me_please"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """
    通用加密函数：
    无论密码多长，先用 SHA256 压缩成 64位 字符串，再交给 Bcrypt。
    这样彻底解决 'password cannot be longer than 72 bytes' 报错。
    """
    # 1. 打印调试信息 (排查到底传进来了什么)
    print(f"DEBUG: 正在加密的原始密码: {password}, 类型: {type(password)}, 长度: {len(password) if password else 0}")

    # 2. SHA256 预处理
    # .encode() 转字节, .hexdigest() 转回字符串
    sha256_password = hashlib.sha256(password.encode('utf-8')).hexdigest()

    # 3. Bcrypt 加密 (这时候输入固定是 64 长度)
    return pwd_context.hash(sha256_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证函数：
    验证时也必须先做同样的 SHA256 处理，否则永远匹配不上。
    """
    sha256_password = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    return pwd_context.verify(sha256_password, hashed_password)


# Token 相关保持不变
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt