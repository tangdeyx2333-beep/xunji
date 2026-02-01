import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.models.sql_models import Base

load_dotenv()

# 使用 SQLite，文件会生成在项目根目录叫 zhiwei.db
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

# check_same_thread=False 是 SQLite 在多线程环境下的特殊配置
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

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