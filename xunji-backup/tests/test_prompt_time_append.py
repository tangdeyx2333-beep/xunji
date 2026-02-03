import re
import asyncio

from app.schemas.chat import ChatRequest
from app.services.chat_services import chat_service


def test_with_current_time_appends_seconds_timestamp():
    out = chat_service._with_current_time("hello")
    assert out.startswith("hello\n\n当前时间：")
    assert re.search(r"当前时间：\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", out)


def test_multimodal_user_text_contains_time(monkeypatch):
    from langchain_core.messages import HumanMessage

    class FakeChunk:
        content = "ok"

    class FakeModel:
        def __init__(self):
            self.seen_messages = None

        async def astream(self, messages):
            self.seen_messages = messages
            yield FakeChunk()

    fake_model = FakeModel()
    monkeypatch.setattr(chat_service, "get_model", lambda name: fake_model)
    monkeypatch.setattr(chat_service, "_with_current_time", lambda t: f"{t}\n\n当前时间：2000-01-01 00:00:00")

    req = ChatRequest(
        user_id="u1",
        message="看看这张图",
        model_name="kimi-k2.5",
        enable_search=False,
        enable_rag=False,
        file_ids=[],
        conversation_id=None,
        parent_id=None,
        files=[
            {
                "name": "a.png",
                "type": "image",
                "mime": "image/png",
                "size": 1,
                "base64": "YWJj",
            }
        ],
    )

    async def run_once():
        async for _ in chat_service.astream_chat_with_model(req, db=None, current_node_id=None):
            break

    asyncio.run(run_once())

    assert fake_model.seen_messages is not None
    human = [m for m in fake_model.seen_messages if isinstance(m, HumanMessage)][-1]
    parts = human.content
    text_parts = [p for p in parts if isinstance(p, dict) and p.get("type") == "text"]
    assert text_parts
    assert text_parts[-1]["text"].endswith("当前时间：2000-01-01 00:00:00")
