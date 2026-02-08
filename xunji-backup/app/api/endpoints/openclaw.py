import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()


class OpenClawChatRequest(BaseModel):
    """
    Parse OpenClaw chat request payload.

    Args:
        message: User message to send to OpenClaw.
    """
    message: str

async def openclaw_stream_generator(message: str) -> AsyncGenerator[str, None]:
    """
    Generate OpenClaw SSE stream response.

    Args:
        message: User message.

    Yields:
        SSE frames, each frame contains a JSON payload with a "content" field.
    """
    response_text = f"【OpenClaw】收到你的消息: {message}。正在为您处理..."
    await asyncio.sleep(0.2)

    for char in response_text:
        await asyncio.sleep(0.02)
        yield f"data: {json.dumps({'content': char})}\n\n"

    yield "data: [DONE]\n\n"

@router.post("/chat")
async def openclaw_chat(request: OpenClawChatRequest):
    """
    Stream OpenClaw chat completion as SSE.

    接收用户消息，返回模拟的 OpenClaw 流式响应。
    目前仅为演示接口，未连接真实 OpenClaw 服务。

    Args:
        request (OpenClawChatRequest): 包含用户消息的请求体

    Returns:
        StreamingResponse: SSE 格式的流式响应，Content-Type 为 text/event-stream
    """
    return StreamingResponse(
        openclaw_stream_generator(request.message),
        media_type="text/event-stream"
    )
