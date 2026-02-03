import base64

import pytest
from fastapi import HTTPException
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints.chat import chat_endpoint
from app.models.sql_models import Base, User
from app.schemas.chat import ChatRequest


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_chat_allows_empty_message_with_files(db_session):
    payload = ChatRequest(
        message="",
        model_name="kimi-k2.5",
        enable_search=False,
        enable_rag=False,
        file_ids=[],
        conversation_id=None,
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

    user = User(id="u1", username="u1", hashed_password="x")
    response = asyncio.run(chat_endpoint(payload, current_user=user, db=db_session))
    assert (payload.message or "").strip() != ""
    assert response.status_code == 200


def test_chat_rejects_empty_message_without_files(db_session):
    payload = ChatRequest(
        message="",
        model_name="kimi-k2.5",
        enable_search=False,
        enable_rag=False,
        file_ids=[],
        conversation_id=None,
        parent_id=None,
        files=[],
    )
    user = User(id="u1", username="u1", hashed_password="x")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(chat_endpoint(payload, current_user=user, db=db_session))
    assert exc.value.status_code == 422
