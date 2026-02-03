import base64

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.sql_models import Base, MessageAttachment
from app.services import attachment_service as attachment_service_mod


@pytest.fixture()
def SessionLocal():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_save_chat_attachments_creates_rows(monkeypatch, SessionLocal):
    db = SessionLocal()

    def fake_upload_bytes(**kwargs):
        return {"key": "k1", "filename": "img.png", "content_type": "image/png", "size": 3, "storage_provider": "aliyun"}

    monkeypatch.setattr(attachment_service_mod.object_storage, "upload_bytes", fake_upload_bytes)

    saved = attachment_service_mod.save_chat_attachments(
        db=db,
        files=[
            {
                "name": "img.png",
                "mime": "image/png",
                "base64": base64.b64encode(b"abc").decode("ascii"),
            }
        ],
        user_id="u1",
        conversation_id="c1",
        message_id="m1",
    )

    rows = db.query(MessageAttachment).all()
    db.close()

    assert len(saved) == 1
    assert len(rows) == 1
    assert rows[0].storage_key == "k1"
    assert rows[0].filename == "img.png"

