import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.endpoints.instructions import (
    create_instruction,
    delete_instruction,
    get_instructions,
    update_instruction,
    AiInstructionCreate,
    AiInstructionUpdate,
)
from app.models.sql_models import AiInstruction, Base, User
import asyncio


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
def test_user():
    return User(id="user1", username="testuser", hashed_password="hashed")


@pytest.fixture()
def another_user():
    return User(id="user2", username="another", hashed_password="hashed")


class TestInstructionCRUD:
    """Test CRUD operations for AI instructions."""

    def test_create_instruction_success(self, db_session, test_user):
        """Test successful creation of an instruction."""
        db_session.add(test_user)
        db_session.commit()

        result = asyncio.run(create_instruction(
            payload=AiInstructionCreate(content="Test instruction"),
            db=db_session,
            current_user=test_user,
        ))

        assert result.content == "Test instruction"
        assert result.sort_order == 1
        assert result.user_id == test_user.id

    def test_create_instruction_empty_content(self, db_session, test_user):
        """Test creation with empty content should fail."""
        db_session.add(test_user)
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(create_instruction(
                payload=AiInstructionCreate(content=""),
                db=db_session,
                current_user=test_user,
            ))
        assert exc.value.status_code == 400
        assert "content 不能为空" in exc.value.detail

    def test_create_multiple_instructions(self, db_session, test_user):
        """Test creating multiple instructions with correct sort order."""
        db_session.add(test_user)
        db_session.commit()

        asyncio.run(create_instruction(
            payload=AiInstructionCreate(content="First instruction"),
            db=db_session,
            current_user=test_user,
        ))
        asyncio.run(create_instruction(
            payload=AiInstructionCreate(content="Second instruction"),
            db=db_session,
            current_user=test_user,
        ))

        instructions = (
            db_session.query(AiInstruction)
            .filter(AiInstruction.user_id == test_user.id)
            .order_by(AiInstruction.sort_order.asc())
            .all()
        )

        assert len(instructions) == 2
        assert instructions[0].content == "First instruction"
        assert instructions[0].sort_order == 1
        assert instructions[1].content == "Second instruction"
        assert instructions[1].sort_order == 2

    def test_get_instructions_empty(self, db_session, test_user):
        """Test getting instructions when user has none."""
        db_session.add(test_user)
        db_session.commit()

        result = asyncio.run(get_instructions(
            db=db_session, current_user=test_user
        ))

        assert result == []

    def test_get_instructions_with_data(self, db_session, test_user):
        """Test getting instructions with existing data."""
        db_session.add(test_user)
        db_session.commit()

        instruction1 = AiInstruction(
            user_id=test_user.id, content="First", sort_order=1
        )
        instruction2 = AiInstruction(
            user_id=test_user.id, content="Second", sort_order=2
        )
        db_session.add_all([instruction1, instruction2])
        db_session.commit()

        result = asyncio.run(get_instructions(
            db=db_session, current_user=test_user
        ))

        assert len(result) == 2
        assert result[0].content == "First"
        assert result[1].content == "Second"

    def test_update_instruction_content(self, db_session, test_user):
        """Test updating instruction content."""
        db_session.add(test_user)
        instruction = AiInstruction(
            user_id=test_user.id, content="Original", sort_order=1
        )
        db_session.add(instruction)
        db_session.commit()

        result = asyncio.run(update_instruction(
            instruction_id=instruction.id,
            payload=AiInstructionUpdate(content="Updated content"),
            db=db_session,
            current_user=test_user,
        ))

        assert result.content == "Updated content"
        assert result.sort_order == 1

    def test_update_instruction_sort_order(self, db_session, test_user):
        """Test updating instruction sort order."""
        db_session.add(test_user)
        instruction = AiInstruction(
            user_id=test_user.id, content="Test", sort_order=1
        )
        db_session.add(instruction)
        db_session.commit()

        result = asyncio.run(update_instruction(
            instruction_id=instruction.id,
            payload=AiInstructionUpdate(sort_order=5),
            db=db_session,
            current_user=test_user,
        ))

        assert result.sort_order == 5

    def test_delete_instruction(self, db_session, test_user):
        """Test soft deleting an instruction."""
        db_session.add(test_user)
        instruction = AiInstruction(
            user_id=test_user.id, content="To be deleted", sort_order=1
        )
        db_session.add(instruction)
        db_session.commit()

        result = asyncio.run(delete_instruction(
            instruction_id=instruction.id,
            db=db_session,
            current_user=test_user,
        ))

        assert result["message"] == "删除成功"

        deleted_instruction = (
            db_session.query(AiInstruction)
            .filter(AiInstruction.id == instruction.id)
            .first()
        )
        assert deleted_instruction.is_deleted is True

    def test_delete_nonexistent_instruction(self, db_session, test_user):
        """Test deleting a non-existent instruction should fail."""
        db_session.add(test_user)
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(delete_instruction(
                instruction_id="nonexistent",
                db=db_session,
                current_user=test_user,
            ))
        assert exc.value.status_code == 404


class TestInstructionPermissionIsolation:
    """Test that users can only access their own instructions."""

    def test_user_cannot_access_other_user_instructions(
        self, db_session, test_user, another_user
    ):
        """Test user cannot see other user's instructions."""
        db_session.add_all([test_user, another_user])
        db_session.commit()

        other_instruction = AiInstruction(
            user_id=another_user.id, content="Other user's instruction", sort_order=1
        )
        db_session.add(other_instruction)
        db_session.commit()

        result = asyncio.run(get_instructions(
            db=db_session, current_user=test_user
        ))

        assert len(result) == 0

    def test_user_cannot_update_other_user_instruction(
        self, db_session, test_user, another_user
    ):
        """Test user cannot update other user's instruction."""
        db_session.add_all([test_user, another_user])
        other_instruction = AiInstruction(
            user_id=another_user.id, content="Other user's instruction", sort_order=1
        )
        db_session.add(other_instruction)
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(update_instruction(
                instruction_id=other_instruction.id,
                payload=AiInstructionUpdate(content="Hacked"),
                db=db_session,
                current_user=test_user,
            ))
        assert exc.value.status_code == 404

    def test_user_cannot_delete_other_user_instruction(
        self, db_session, test_user, another_user
    ):
        """Test user cannot delete other user's instruction."""
        db_session.add_all([test_user, another_user])
        other_instruction = AiInstruction(
            user_id=another_user.id, content="Other user's instruction", sort_order=1
        )
        db_session.add(other_instruction)
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            asyncio.run(delete_instruction(
                instruction_id=other_instruction.id,
                db=db_session,
                current_user=test_user,
            ))
        assert exc.value.status_code == 404


class TestInstructionPromptInjection:
    """Test that instructions are properly injected into prompts."""

    def test_get_user_instructions_empty(self, db_session, test_user):
        """Test getting instructions when user has none returns empty string."""
        from app.services.chat_services import chat_service

        db_session.add(test_user)
        db_session.commit()

        result = chat_service._get_user_instructions(db_session, test_user.id)
        assert result == ""

    def test_get_user_instructions_formatting(self, db_session, test_user):
        """Test instructions are properly formatted."""
        from app.services.chat_services import chat_service

        db_session.add(test_user)
        instructions = [
            AiInstruction(user_id=test_user.id, content="First instruction", sort_order=1),
            AiInstruction(user_id=test_user.id, content="Second instruction", sort_order=2),
            AiInstruction(user_id=test_user.id, content="Third instruction", sort_order=3),
        ]
        db_session.add_all(instructions)
        db_session.commit()

        result = chat_service._get_user_instructions(db_session, test_user.id)

        assert "额外指令：" in result
        assert "1. First instruction" in result
        assert "2. Second instruction" in result
        assert "3. Third instruction" in result

    def test_get_user_instructions_sorting(self, db_session, test_user):
        """Test instructions are sorted by sort_order and created_at."""
        from app.services.chat_services import chat_service

        db_session.add(test_user)
        instructions = [
            AiInstruction(user_id=test_user.id, content="Order 3", sort_order=3),
            AiInstruction(user_id=test_user.id, content="Order 1", sort_order=1),
            AiInstruction(user_id=test_user.id, content="Order 2", sort_order=2),
        ]
        db_session.add_all(instructions)
        db_session.commit()

        result = chat_service._get_user_instructions(db_session, test_user.id)

        lines = result.split("\n")
        assert "1. Order 1" in lines[1]
        assert "2. Order 2" in lines[2]
        assert "3. Order 3" in lines[3]

    def test_get_user_instructions_excludes_deleted(self, db_session, test_user):
        """Test deleted instructions are not included."""
        from app.services.chat_services import chat_service

        db_session.add(test_user)
        instructions = [
            AiInstruction(user_id=test_user.id, content="Active", sort_order=1, is_deleted=False),
            AiInstruction(user_id=test_user.id, content="Deleted", sort_order=2, is_deleted=True),
        ]
        db_session.add_all(instructions)
        db_session.commit()

        result = chat_service._get_user_instructions(db_session, test_user.id)

        assert "Active" in result
        assert "Deleted" not in result
        assert result.count(".") == 1

    def test_get_user_instructions_multiline_content(self, db_session, test_user):
        """Test instructions with multiline content are handled correctly."""
        from app.services.chat_services import chat_service

        db_session.add(test_user)
        multiline_content = """This is a multiline instruction.
It has multiple lines.
Each line should be preserved."""
        instruction = AiInstruction(
            user_id=test_user.id, content=multiline_content, sort_order=1
        )
        db_session.add(instruction)
        db_session.commit()

        result = chat_service._get_user_instructions(db_session, test_user.id)

        assert "1. This is a multiline instruction." in result
        assert "It has multiple lines." in result
        assert "Each line should be preserved." in result
