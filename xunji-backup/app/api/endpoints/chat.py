import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse  # ★ 引入流式响应
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.sql_models import Conversation, Message, User, TreeNode, gen_uuid
from app.schemas.chat import ChatRequest
from app.services.chat_services import chat_service

router = APIRouter()


@router.post("/chat")  # 注意：这里不再指定 response_model，因为返回的是 Stream
async def chat_endpoint(
        request: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # 1. 基础信息处理
    request.user_id = current_user.id

    # 2. 会话处理 (如果不存在则创建)
    if request.conversation_id is None:
        conversation = Conversation(
            id=gen_uuid(),
            title="新对话",  # 实际场景可以用模型生成标题
            user_id=request.user_id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        request.conversation_id = conversation.id

    # 3. ★ 立即保存【用户消息】 (防止流中断导致用户消息丢失)
    user_message = Message(
        id=gen_uuid(),
        conversation_id=request.conversation_id,
        role="user",
        content=request.message
    )
    db.add(user_message)
    
    # ★ 新增：创建树节点（用户）
    user_node = TreeNode(
        id=gen_uuid(),
        conversation_id=request.conversation_id,
        message_id=user_message.id,
        parent_id=request.parent_id  # 挂载到前端传来的父节点上
    )
    db.add(user_node)
    
    db.commit()
    db.refresh(user_node) # 获取ID

    # 4. 定义流式生成器
    async def response_generator():
        full_ai_response = ""

        # 4.1 发送会话ID 和 用户节点ID (前端需要更新 currentLeafId)
        # SSE 格式: data: {json}\n\n
        yield f"data: {json.dumps({'session_id': request.conversation_id, 'user_node_id': user_node.id})}\n\n"

        # 4.2 调用 Service 获取流 (传入 user_node.id 作为上下文终点)
        # 注意：这里我们修改 service 方法，让它接受 current_node_id 而不是只靠 limit
        async for chunk in chat_service.astream_chat_with_model(request, db, current_node_id=user_node.id):
            if chunk:
                full_ai_response += chunk
                # 构建 SSE 数据包
                yield f"data: {json.dumps({'content': chunk})}\n\n"

        # 4.3 ★ 流结束后，保存【AI 消息】到数据库
        ai_message = Message(
            id=gen_uuid(),
            conversation_id=request.conversation_id,
            role="ai",  # 也就是 assistant
            content=full_ai_response
        )
        db.add(ai_message)
        
        # ★ 新增：创建树节点（AI）
        ai_node = TreeNode(
            id=gen_uuid(),
            conversation_id=request.conversation_id,
            message_id=ai_message.id,
            parent_id=user_node.id  # AI 回复挂在用户消息后面
        )
        db.add(ai_node)
        db.commit()
        db.refresh(ai_node)

        # 4.4 发送结束信号，包含 AI 的节点 ID
        yield f"data: {json.dumps({'ai_node_id': ai_node.id})}\n\n"
        yield "data: [DONE]\n\n"

    # 5. 返回流式响应
    return StreamingResponse(
        response_generator(),
        media_type="text/event-stream"
    )