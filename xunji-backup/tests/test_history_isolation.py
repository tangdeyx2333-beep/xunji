import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.endpoints import history as history_router
from app.db.session import get_db
from app.models.sql_models import Base, Conversation, User

@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine

@pytest.fixture()
def SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def db_session(SessionLocal):
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture()
def app(SessionLocal, db_session):
    application = FastAPI()
    application.include_router(history_router.router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db
    return application

def test_get_conversations_isolation(app, db_session):
    # 1. 创建两个用户
    user1 = User(id="user1", username="u1", hashed_password="x", is_anonymous=False)
    user2 = User(id="user2", username="u2", hashed_password="x", is_anonymous=False)
    db_session.add(user1)
    db_session.add(user2)
    
    # 2. 为每个用户创建会话
    c1 = Conversation(id="c1", title="User 1 Conv", user_id="user1")
    c2 = Conversation(id="c2", title="User 2 Conv", user_id="user2")
    db_session.add(c1)
    db_session.add(c2)
    db_session.commit()

    client = TestClient(app)

    # 3. 模拟以 User 1 身份请求
    async def override_current_user1():
        return user1
    app.dependency_overrides[get_current_user] = override_current_user1
    
    response = client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "c1"
    assert data[0]["title"] == "User 1 Conv"

    # 4. 模拟以 User 2 身份请求
    async def override_current_user2():
        return user2
    app.dependency_overrides[get_current_user] = override_current_user2
    
    response = client.get("/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "c2"
    assert data[0]["title"] == "User 2 Conv"

def test_get_messages_security(app, db_session):
    # 1. 创建两个用户和对应的会话
    user1 = User(id="u1", username="u1", hashed_password="x")
    user2 = User(id="u2", username="u2", hashed_password="x")
    c1 = Conversation(id="c1", title="U1 Conv", user_id="u1")
    db_session.add_all([user1, user2, c1])
    db_session.commit()

    client = TestClient(app)

    # 2. 以 User 2 身份尝试获取 User 1 的消息
    async def override_current_user2():
        return user2
    app.dependency_overrides[get_current_user] = override_current_user2

    response = client.get("/api/conversations/c1/messages")
    assert response.status_code == 404 # 应该找不到（因为过滤了 user_id）

def test_delete_conversation_security(app, db_session):
    # 1. 创建两个用户和对应的会话
    user1 = User(id="u1", username="u1", hashed_password="x")
    user2 = User(id="u2", username="u2", hashed_password="x")
    c1 = Conversation(id="c1", title="U1 Conv", user_id="u1")
    db_session.add_all([user1, user2, c1])
    db_session.commit()

    client = TestClient(app)

    # 2. 以 User 2 身份尝试删除 User 1 的会话
    async def override_current_user2():
        return user2
    app.dependency_overrides[get_current_user] = override_current_user2

    response = client.delete("/api/conversations/c1")
    assert response.status_code == 404
    
    # 确认会话未被删除
    db_session.refresh(c1)
    assert c1.is_deleted == False
