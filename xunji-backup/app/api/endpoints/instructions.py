from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.sql_models import AiInstruction, Conversation, ConversationAiInstruction, User

router = APIRouter()


class AiInstructionCreate(BaseModel):
    content: str


class AiInstructionUpdate(BaseModel):
    content: Optional[str] = None
    sort_order: Optional[int] = None


class AiInstructionDTO(BaseModel):
    id: str
    content: str
    sort_order: int

    class Config:
        from_attributes = True


class ConversationAiInstructionCreate(BaseModel):
    content: str


class ConversationAiInstructionUpdate(BaseModel):
    content: Optional[str] = None
    sort_order: Optional[int] = None


class ConversationAiInstructionDTO(BaseModel):
    id: str
    content: str
    sort_order: int

    class Config:
        from_attributes = True


def _get_owned_conversation(db: Session, conversation_id: str, current_user: User) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .filter(Conversation.user_id == current_user.id)
        .filter(Conversation.is_deleted == False)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@router.get("/instructions", response_model=List[AiInstructionDTO])
async def get_instructions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(AiInstruction)
        .filter(AiInstruction.user_id == current_user.id)
        .filter(AiInstruction.is_deleted == False)
        .order_by(AiInstruction.sort_order.asc(), AiInstruction.created_at.asc())
        .all()
    )


@router.post("/instructions", response_model=AiInstructionDTO)
async def create_instruction(
    payload: AiInstructionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")

    max_sort = (
        db.query(func.max(AiInstruction.sort_order))
        .filter(AiInstruction.user_id == current_user.id)
        .filter(AiInstruction.is_deleted == False)
        .scalar()
    )
    next_sort = int(max_sort or 0) + 1

    row = AiInstruction(user_id=current_user.id, content=content, sort_order=next_sort)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/instructions/{instruction_id}", response_model=AiInstructionDTO)
async def update_instruction(
    instruction_id: str,
    payload: AiInstructionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(AiInstruction)
        .filter(AiInstruction.id == instruction_id)
        .filter(AiInstruction.user_id == current_user.id)
        .filter(AiInstruction.is_deleted == False)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="指令不存在")

    if payload.content is not None:
        content = (payload.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content 不能为空")
        row.content = content

    if payload.sort_order is not None:
        row.sort_order = int(payload.sort_order)

    db.commit()
    db.refresh(row)
    return row


@router.delete("/instructions/{instruction_id}")
async def delete_instruction(
    instruction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = (
        db.query(AiInstruction)
        .filter(AiInstruction.id == instruction_id)
        .filter(AiInstruction.user_id == current_user.id)
        .filter(AiInstruction.is_deleted == False)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="指令不存在")

    row.is_deleted = True
    db.commit()
    return {"message": "删除成功"}


@router.get("/conversations/{conversation_id}/instructions", response_model=List[ConversationAiInstructionDTO])
async def get_conversation_instructions(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_conversation(db, conversation_id, current_user)
    return (
        db.query(ConversationAiInstruction)
        .filter(ConversationAiInstruction.conversation_id == conversation_id)
        .filter(ConversationAiInstruction.user_id == current_user.id)
        .filter(ConversationAiInstruction.is_deleted == False)
        .order_by(ConversationAiInstruction.sort_order.asc(), ConversationAiInstruction.created_at.asc())
        .all()
    )


@router.post("/conversations/{conversation_id}/instructions", response_model=ConversationAiInstructionDTO)
async def create_conversation_instruction(
    conversation_id: str,
    payload: ConversationAiInstructionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_conversation(db, conversation_id, current_user)
    content = (payload.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")

    max_sort = (
        db.query(func.max(ConversationAiInstruction.sort_order))
        .filter(ConversationAiInstruction.conversation_id == conversation_id)
        .filter(ConversationAiInstruction.user_id == current_user.id)
        .filter(ConversationAiInstruction.is_deleted == False)
        .scalar()
    )
    next_sort = int(max_sort or 0) + 1

    row = ConversationAiInstruction(
        conversation_id=conversation_id,
        user_id=current_user.id,
        content=content,
        sort_order=next_sort,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put(
    "/conversations/{conversation_id}/instructions/{instruction_id}",
    response_model=ConversationAiInstructionDTO,
)
async def update_conversation_instruction(
    conversation_id: str,
    instruction_id: str,
    payload: ConversationAiInstructionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_conversation(db, conversation_id, current_user)
    row = (
        db.query(ConversationAiInstruction)
        .filter(ConversationAiInstruction.id == instruction_id)
        .filter(ConversationAiInstruction.conversation_id == conversation_id)
        .filter(ConversationAiInstruction.user_id == current_user.id)
        .filter(ConversationAiInstruction.is_deleted == False)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="指令不存在")

    if payload.content is not None:
        content = (payload.content or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content 不能为空")
        row.content = content

    if payload.sort_order is not None:
        row.sort_order = int(payload.sort_order)

    db.commit()
    db.refresh(row)
    return row


@router.delete("/conversations/{conversation_id}/instructions/{instruction_id}")
async def delete_conversation_instruction(
    conversation_id: str,
    instruction_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_owned_conversation(db, conversation_id, current_user)
    row = (
        db.query(ConversationAiInstruction)
        .filter(ConversationAiInstruction.id == instruction_id)
        .filter(ConversationAiInstruction.conversation_id == conversation_id)
        .filter(ConversationAiInstruction.user_id == current_user.id)
        .filter(ConversationAiInstruction.is_deleted == False)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="指令不存在")

    row.is_deleted = True
    db.commit()
    return {"message": "删除成功"}

