import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints.instructions import (
    ConversationAiInstructionCreate,
    ConversationAiInstructionUpdate,
    create_conversation_instruction,
    delete_conversation_instruction,
    get_conversation_instructions,
    update_conversation_instruction,
)
from app.models.sql_models import AiInstruction, Base, Conversation, ConversationAiInstruction, User


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


@pytest.fixture()
def user1():
    return User(id="u1", username="u1", hashed_password="x")


@pytest.fixture()
def user2():
    return User(id="u2", username="u2", hashed_password="x")


@pytest.fixture()
def conv1(user1):
    return Conversation(id="c1", title="t1", user_id=user1.id)


class TestConversationInstructionCRUD:
    def test_create_and_list(self, db_session, user1, conv1):
        db_session.add_all([user1, conv1])
        db_session.commit()

        asyncio.run(
            create_conversation_instruction(
                conversation_id=conv1.id,
                payload=ConversationAiInstructionCreate(content="A"),
                db=db_session,
                current_user=user1,
            )
        )
        asyncio.run(
            create_conversation_instruction(
                conversation_id=conv1.id,
                payload=ConversationAiInstructionCreate(content="B"),
                db=db_session,
                current_user=user1,
            )
        )

        rows = asyncio.run(get_conversation_instructions(conversation_id=conv1.id, db=db_session, current_user=user1))
        assert [r.content for r in rows] == ["A", "B"]
        assert [r.sort_order for r in rows] == [1, 2]

    def test_update_content_and_sort(self, db_session, user1, conv1):
        db_session.add_all([user1, conv1])
        db_session.commit()

        created = asyncio.run(
            create_conversation_instruction(
                conversation_id=conv1.id,
                payload=ConversationAiInstructionCreate(content="Old"),
                db=db_session,
                current_user=user1,
            )
        )

        updated = asyncio.run(
            update_conversation_instruction(
                conversation_id=conv1.id,
                instruction_id=created.id,
                payload=ConversationAiInstructionUpdate(content="New", sort_order=5),
                db=db_session,
                current_user=user1,
            )
        )
        assert updated.content == "New"
        assert updated.sort_order == 5

    def test_delete_soft(self, db_session, user1, conv1):
        db_session.add_all([user1, conv1])
        db_session.commit()

        created = asyncio.run(
            create_conversation_instruction(
                conversation_id=conv1.id,
                payload=ConversationAiInstructionCreate(content="X"),
                db=db_session,
                current_user=user1,
            )
        )
        resp = asyncio.run(
            delete_conversation_instruction(
                conversation_id=conv1.id,
                instruction_id=created.id,
                db=db_session,
                current_user=user1,
            )
        )
        assert resp["message"] == "删除成功"

        row = db_session.query(ConversationAiInstruction).filter(ConversationAiInstruction.id == created.id).first()
        assert row is not None
        assert row.is_deleted is True

        rows = asyncio.run(get_conversation_instructions(conversation_id=conv1.id, db=db_session, current_user=user1))
        assert rows == []

    def test_reject_empty_content(self, db_session, user1, conv1):
        db_session.add_all([user1, conv1])
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                create_conversation_instruction(
                    conversation_id=conv1.id,
                    payload=ConversationAiInstructionCreate(content=""),
                    db=db_session,
                    current_user=user1,
                )
            )
        assert exc.value.status_code == 400


class TestConversationInstructionPermission:
    def test_cannot_access_other_users_conversation(self, db_session, user1, user2, conv1):
        db_session.add_all([user1, user2, conv1])
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_conversation_instructions(conversation_id=conv1.id, db=db_session, current_user=user2))
        assert exc.value.status_code == 404

    def test_cannot_create_on_other_users_conversation(self, db_session, user1, user2, conv1):
        db_session.add_all([user1, user2, conv1])
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                create_conversation_instruction(
                    conversation_id=conv1.id,
                    payload=ConversationAiInstructionCreate(content="hack"),
                    db=db_session,
                    current_user=user2,
                )
            )
        assert exc.value.status_code == 404


class TestConversationInstructionPromptInjection:
    def test_combined_instructions_include_conversation(self, db_session, user1, conv1):
        from app.services.chat_services import chat_service

        db_session.add_all([user1, conv1])
        db_session.add(AiInstruction(user_id=user1.id, content="Global 1", sort_order=1))
        db_session.add(ConversationAiInstruction(conversation_id=conv1.id, user_id=user1.id, content="Session 1", sort_order=1))
        db_session.commit()

        text = chat_service._get_combined_instructions(db_session, user1.id, conv1.id)
        assert "额外指令：" in text
        assert "会话指令：" in text
        assert "Global 1" in text
        assert "Session 1" in text

