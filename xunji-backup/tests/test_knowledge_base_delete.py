import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.api.endpoints import upload as upload_router
from app.db.session import get_db
from app.models.sql_models import Base, FileRecord, User


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
def app(SessionLocal):
    application = FastAPI()
    application.include_router(upload_router.router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db

    seed = SessionLocal()
    seed.add(User(id="u1", username="u1", hashed_password="x"))
    seed.add(User(id="u2", username="u2", hashed_password="x"))
    seed.commit()
    seed.close()

    async def override_current_user():
        return User(id="u1", username="u1", hashed_password="x")

    application.dependency_overrides[get_current_user] = override_current_user
    return application


def test_delete_file_requires_owner(app, SessionLocal, monkeypatch):
    def fake_delete_doc(file_id):
        return None

    monkeypatch.setattr(upload_router.rag_service, "delete_doc", fake_delete_doc)

    db = SessionLocal()
    db.add(FileRecord(id="f1", user_id="u2", filename="a.pdf", file_path=".", file_size=1, is_deleted=False))
    db.commit()
    db.close()

    client = TestClient(app)
    r = client.delete("/api/files/f1")
    assert r.status_code == 403


def test_clear_kb_requires_confirm(app, SessionLocal, monkeypatch):
    def fake_delete_docs(file_ids):
        return None

    monkeypatch.setattr(upload_router.rag_service, "delete_docs", fake_delete_docs)

    db = SessionLocal()
    db.add(FileRecord(id="f1", user_id="u1", filename="a.pdf", file_path=".", file_size=1, is_deleted=False))
    db.commit()
    db.close()

    client = TestClient(app)
    r = client.post("/api/knowledge-base/clear", json={"confirm": False})
    assert r.status_code == 400


def test_clear_kb_marks_deleted_and_calls_vector_delete(app, SessionLocal, monkeypatch):
    called = {"ids": None}

    def fake_delete_docs(file_ids):
        called["ids"] = list(file_ids)

    monkeypatch.setattr(upload_router.rag_service, "delete_docs", fake_delete_docs)

    db = SessionLocal()
    db.add(FileRecord(id="f1", user_id="u1", filename="a.pdf", file_path=".", file_size=1, is_deleted=False))
    db.add(FileRecord(id="f2", user_id="u1", filename="b.pdf", file_path=".", file_size=1, is_deleted=False))
    db.commit()
    db.close()

    client = TestClient(app)
    r = client.post("/api/knowledge-base/clear", json={"confirm": True})
    assert r.status_code == 200

    check = SessionLocal()
    rows = check.query(FileRecord).filter(FileRecord.user_id == "u1").all()
    check.close()
    assert all(r.is_deleted for r in rows)
    assert set(called["ids"] or []) == {"f1", "f2"}

