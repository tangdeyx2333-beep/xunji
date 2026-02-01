from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.db.session import get_db
from app.models.sql_models import Conversation, Message, TreeNode

router = APIRouter()


# --- 定义响应模型 (DTO) ---
class ConversationDTO(BaseModel):
    id: str
    title: str
    updated_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True  # 让 Pydantic 支持直接读取 SQLAlchemy 对象


class MessageDTO(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    type: str
    node_id: Optional[str] = None # 新增节点ID
    parent_node_id: Optional[str] = None # 新增父节点ID

    class Config:
        from_attributes = True


# --- 接口 1: 获取会话列表 (侧边栏) ---
@router.get("/conversations", response_model=List[ConversationDTO])
async def get_conversations(
        limit: int = 20,
        db: Session = Depends(get_db)
):
    """
    获取所有会话列表，按更新时间倒序排列（最近聊的在最上面）
    """
    conversations = db.query(Conversation) \
        .filter(Conversation.is_deleted == False) \
        .order_by(Conversation.updated_at.desc()) \
        .limit(limit) \
        .all()
    return conversations


# --- 接口 2: 获取指定会话的消息记录 (点击进入聊天) ---
@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageDTO])
async def get_messages(
        conversation_id: str,
        db: Session = Depends(get_db)
):
    """
    加载具体的聊天记录
    """
    # 1. 检查会话是否存在
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 2. 查消息 (按时间正序，最旧的在上面)
    # 并且我们需要 Join TreeNode 来获取 node_id
    # 注意：这里我们使用 outerjoin，因为旧消息可能没有 node 记录
    results = db.query(Message, TreeNode.id.label("node_id"), TreeNode.parent_id.label("parent_node_id")) \
        .outerjoin(TreeNode, TreeNode.message_id == Message.id) \
        .filter(Message.conversation_id == conversation_id) \
        .order_by(Message.created_at.asc()) \
        .all()
    
    # 构造 DTO
    messages_dto = []
    for msg, node_id, parent_node_id in results:
        dto = MessageDTO.model_validate(msg)
        dto.node_id = node_id
        dto.parent_node_id = parent_node_id
        messages_dto.append(dto)

    return messages_dto


# --- 接口 3: 删除会话 (软删除) ---
@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
        conversation_id: str,
        db: Session = Depends(get_db)
):
    """
    删除会话（前端点击垃圾桶图标）
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 执行软删除
    conversation.is_deleted = True
    db.commit()
    return {"message": "会话已删除", "conversation_id": conversation_id}


# --- 接口 4: 根据节点ID获取完整路径消息 (面包屑) ---
@router.get("/tree/path/{node_id}", response_model=List[MessageDTO])
async def get_node_path(node_id: str, db: Session = Depends(get_db)):
    """
    根据指定节点ID，向上递归获取完整路径上的所有消息（从根节点 -> 当前节点）
    """
    from sqlalchemy import text
    
    # 检查节点是否存在
    target_node = db.query(TreeNode).filter(TreeNode.id == node_id).first()
    if not target_node:
        raise HTTPException(status_code=404, detail="Node not found")

    # 使用 CTE 递归查询路径
    # 注意：SQLite 和 Postgres 都支持 WITH RECURSIVE
    recursive_query = text("""
        WITH RECURSIVE path_cte AS (
            -- 锚点成员：从目标节点开始
            SELECT t.id, t.parent_id, t.message_id, 0 as level
            FROM tree_nodes t
            WHERE t.id = :target_id
            
            UNION ALL
            
            -- 递归成员：向上查找父节点
            SELECT t.id, t.parent_id, t.message_id, pc.level + 1
            FROM tree_nodes t
            JOIN path_cte pc ON t.id = pc.parent_id
        )
        SELECT pc.id as node_id, pc.parent_id as parent_node_id, 
               m.id, m.role, m.content, m.created_at, m.type, m.conversation_id
        FROM path_cte pc
        JOIN messages m ON pc.message_id = m.id
        ORDER BY pc.level DESC; -- level越大说明越靠上（根节点level最大），所以倒序排列就是 从根->叶子
    """)
    
    results = db.execute(recursive_query, {"target_id": node_id}).fetchall()
    
    # 构造返回
    path_messages = []
    for row in results:
        # 手动映射 SQLAlchemy Row 到 Pydantic 模型
        # 注意：db.execute 返回的是 RowProxy / Row，可以直接按属性访问
        dto = MessageDTO(
            id=row.id,
            role=row.role,
            content=row.content,
            created_at=datetime.fromisoformat(str(row.created_at)) if isinstance(row.created_at, str) else row.created_at,
            type=row.type,
            node_id=row.node_id,
            parent_node_id=row.parent_node_id
        )
        path_messages.append(dto)
        
    return path_messages
