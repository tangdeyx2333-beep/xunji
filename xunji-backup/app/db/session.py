import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
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
engine = create_engine(_normalized_database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 自动建表 把继承Base的类给当作表建立了(相当于 Hibernate ddl-auto)
def init_db():
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    print(f"当前数据库中的表有: {inspector.get_table_names()}")
    print("数据库表结构已创建成功！")

# 依赖注入用的函数 (给 FastAPI Depends 用)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
