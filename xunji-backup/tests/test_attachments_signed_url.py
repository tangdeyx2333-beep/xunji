import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.endpoints import attachments as attachments_router
from app.db.session import get_db
from app.models.sql_models import Base, MessageAttachment, User


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
    application.include_router(attachments_router.router, prefix="/api")

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


def test_signed_url_requires_owner(app, db_session, monkeypatch):
    other_user = User(id="u2", username="u2", hashed_password="x")
    db_session.add(other_user)
    db_session.commit()

    att = MessageAttachment(
        id="a1",
        conversation_id="c1",
        message_id="m1",
        user_id="u2",
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
    r = client.get("/api/attachments/a1/signed-url")
    assert r.status_code == 403


def test_signed_url_expiry_clamp(app, db_session, monkeypatch):
    att = MessageAttachment(
        id="a2",
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

    from app.core import config as config_mod
    from app.api.endpoints import attachments as attachments_mod

    config_mod.SIGNED_URL_EXPIRES_SECONDS_MAX = 10
    attachments_mod.SIGNED_URL_EXPIRES_SECONDS_MAX = 10

    called = {}

    def fake_sign_get_url(*, key: str, expires_seconds: int):
        called["key"] = key
        called["expires_seconds"] = expires_seconds
        return "https://signed"

    monkeypatch.setattr(attachments_mod.aliyun_oss_service, "sign_get_url", fake_sign_get_url)

    client = TestClient(app)
    r = client.get("/api/attachments/a2/signed-url?expires_seconds=9999")
    assert r.status_code == 200
    data = r.json()
    assert data["url"] == "https://signed"
    assert called["expires_seconds"] == 10
