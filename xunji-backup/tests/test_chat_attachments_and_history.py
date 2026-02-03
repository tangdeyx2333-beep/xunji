import base64
import json
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.endpoints import chat as chat_router
from app.api.endpoints import history as history_router
from app.db.session import get_db
from app.models.sql_models import Base, Conversation, Message, MessageAttachment, TreeNode, User
from app.schemas.chat import ChatRequest


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
def app(SessionLocal, db_session, monkeypatch):
    application = FastAPI()
    application.include_router(chat_router.router, prefix="/api")
    application.include_router(history_router.router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db

    user = User(id="u1", username="u1", hashed_password="x")
    db_session.add(user)
    db_session.commit()

    async def override_current_user():
        return user

    application.dependency_overrides[get_current_user] = override_current_user
    return application


def test_chat_attachment_saved_after_ai(app, db_session, monkeypatch):
    from app.api.endpoints import chat as chat_mod

    chat_mod.config.OBJECT_STORAGE_PROVIDER = "aliyun"

    seen_files = {"v": False}

    async def fake_stream(*args, **kwargs):
        req = args[0] if args else None
        if req is not None and getattr(req, "files", None):
            seen_files["v"] = True
        yield "hi"

    monkeypatch.setattr(chat_mod.chat_service, "astream_chat_with_model", fake_stream)

    saved_called = {"v": False}

    def fake_save_chat_attachments(**kwargs):
        saved_called["v"] = True
        return [
            {
                "id": "a1",
                "filename": "img.png",
                "mime": "image/png",
                "size": 3,
                "storage_provider": "aliyun",
                "storage_key": "k1",
            }
        ]

    monkeypatch.setattr(chat_mod, "save_chat_attachments", fake_save_chat_attachments)

    conv = Conversation(id="c1", title="t", user_id="u1")
    user_message = Message(id="m1", conversation_id="c1", role="user", content="look", type="text")
    user_node = TreeNode(id="n1", conversation_id="c1", message_id="m1", parent_id=None)
    db_session.add(conv)
    db_session.add(user_message)
    db_session.add(user_node)
    db_session.commit()

    request = ChatRequest(
        user_id="u1",
        message="",
        model_name="kimi-k2.5",
        enable_search=False,
        enable_rag=False,
        file_ids=[],
        conversation_id="c1",
        parent_id=None,
        files=[
            {
                "name": "img.png",
                "type": "image",
                "mime": "image/png",
                "size": 3,
                "base64": base64.b64encode(b"abc").decode("ascii"),
            }
        ],
    )

    async def collect():
        chunks = []
        async for s in chat_mod.chat_response_generator(
            request=request,
            db=db_session,
            user_node=user_node,
            user_message=user_message,
            is_new_conversation=False,
        ):
            chunks.append(s)
        return "".join(chunks)

    body = asyncio.run(collect())

    assert seen_files["v"] is True
    assert saved_called["v"] is True
    assert "user_attachments_saved" in body


def test_history_returns_attachment_metadata_no_url(app, db_session):
    conv = Conversation(id="c1", title="t", user_id="u1")
    m = Message(id="m1", conversation_id="c1", role="user", content="x", type="text")
    db_session.add(conv)
    db_session.add(m)
    db_session.commit()

    att = MessageAttachment(
        id="a1",
        conversation_id="c1",
        message_id="m1",
        user_id="u1",
        filename="x.png",
        mime="image/png",
        size=1,
        storage_provider="aliyun",
        storage_key="k1",
        url="",
    )
    db_session.add(att)
    db_session.commit()

    client = TestClient(app)
    r = client.get("/api/conversations/c1/messages")
    assert r.status_code == 200
    msgs = r.json()
    assert msgs[0]["attachments"][0]["filename"] == "x.png"
    assert msgs[0]["attachments"][0]["storage_key"] == "k1"
    assert "url" not in msgs[0]["attachments"][0]
