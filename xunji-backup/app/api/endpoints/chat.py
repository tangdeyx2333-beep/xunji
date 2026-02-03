import json
import base64
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse  # ★ 引入流式响应
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.sql_models import Conversation, Message, User, TreeNode, MessageAttachment, gen_uuid
from app.schemas.chat import ChatRequest
from app.services.chat_services import chat_service
from app.services.title_generator import title_generator # ★ 引入标题生成服务
from app.db.session import SessionLocal # 引入 SessionLocal 用于后台任务
from app.core import config
from app.services.object_storage import object_storage
from app.services.attachment_service import save_chat_attachments

router = APIRouter()


async def chat_response_generator(
    *,
    request: ChatRequest,
    db: Session,
    user_node: TreeNode,
    user_message: Message,
    is_new_conversation: bool,
):
    full_ai_response = ""

    yield f"data: {json.dumps({'session_id': request.conversation_id, 'user_node_id': user_node.id})}\n\n"

    async for chunk in chat_service.astream_chat_with_model(request, db, current_node_id=user_node.id):
        if chunk:
            full_ai_response += chunk
            yield f"data: {json.dumps({'content': chunk})}\n\n"

    ai_message = Message(
        id=gen_uuid(),
        conversation_id=request.conversation_id,
        role="ai",
        content=full_ai_response
    )
    db.add(ai_message)

    ai_node = TreeNode(
        id=gen_uuid(),
        conversation_id=request.conversation_id,
        message_id=ai_message.id,
        parent_id=user_node.id
    )
    db.add(ai_node)
    db.commit()
    db.refresh(ai_node)

    yield f"data: {json.dumps({'ai_node_id': ai_node.id})}\n\n"

    saved_attachments = save_chat_attachments(
        db=db,
        files=request.files,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        message_id=user_message.id,
    )
    if saved_attachments:
        yield f"data: {json.dumps({'user_attachments_saved': saved_attachments})}\n\n"

    if is_new_conversation:
        try:
            new_title = await title_generator.generate_title(request.message, full_ai_response)
            with SessionLocal() as background_db:
                conv = background_db.query(Conversation).filter(Conversation.id == request.conversation_id).first()
                if conv:
                    conv.title = new_title
                    background_db.commit()
            yield f"data: {json.dumps({'new_title': new_title})}\n\n"
        except Exception as e:
            print(f"Failed to generate title: {e}")

    yield "data: [DONE]\n\n"


@router.post("/chat")  # 注意：这里不再指定 response_model，因为返回的是 Stream
async def chat_endpoint(
        request: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    # 1. 基础信息处理
    request.user_id = current_user.id
    message_text = (request.message or "").strip()
    if not message_text:
        if request.files and len(request.files) > 0:
            names = [f.get("name") for f in request.files if isinstance(f, dict) and f.get("name")]
            suffix = f"：{', '.join(names[:3])}" if names else ""
            request.message = f"（用户发送了附件{suffix}）"
        else:
            raise HTTPException(status_code=422, detail="message 不能为空")

    # 2. 会话处理 (如果不存在则创建)
    is_new_conversation = request.conversation_id is None # 标记是否为新会话
    if is_new_conversation:
        conversation = Conversation(
            id=gen_uuid(),
            title="新对话",  # 初始标题，稍后异步更新
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

    # 5. 返回流式响应
    return StreamingResponse(
        chat_response_generator(
            request=request,
            db=db,
            user_node=user_node,
            user_message=user_message,
            is_new_conversation=is_new_conversation,
        ),
        media_type="text/event-stream"
    )
