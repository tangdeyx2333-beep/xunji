import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.models.sql_models import Base

load_dotenv(override=False)

SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _normalize_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        db_path = url.database
        if not db_path:
            raise ValueError("SQLALCHEMY_DATABASE_URL for sqlite must include a database file path.")
        if db_path != ":memory:":
            path = Path(db_path)
            if not path.is_absolute():
                path = (_PROJECT_ROOT / path).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=path.as_posix())
    return str(url)

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("SQLALCHEMY_DATABASE_URL is required. See .env.example for a working default.")

_normalized_database_url = _normalize_database_url(SQLALCHEMY_DATABASE_URL)
_connect_args = {"check_same_thread": False} if _normalized_database_url.startswith("sqlite") else {}

# 配置连接池参数以解决连接池耗尽问题
engine = create_engine(
    _normalized_database_url, 
    connect_args=_connect_args,
    # 连接池配置
    pool_size=20,                    # 基础连接池大小
    max_overflow=30,                 # 最大溢出连接数
    pool_timeout=60,                 # 连接超时时间（秒）
    pool_recycle=3600,               # 连接回收时间（秒）
    pool_pre_ping=True               # 连接预检查
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 自动建表 把继承Base的类给当作表建立了(相当于 Hibernate ddl-auto)
def init_db():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as connection:
            if "device_id" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN device_id VARCHAR"))
                connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_device_id ON users (device_id)"))
            if "is_anonymous" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_anonymous BOOLEAN DEFAULT 1"))

# 依赖注入用的函数 (给 FastAPI Depends 用)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
