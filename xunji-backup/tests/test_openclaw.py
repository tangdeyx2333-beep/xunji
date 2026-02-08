from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_openclaw_chat():
    """
    测试 OpenClaw 独立聊天接口
    验证：
    1. 状态码 200
    2. Content-Type 为 text/event-stream
    3. 返回内容包含模拟回复结构
    """
    response = client.post(
        "/api/openclaw/chat",
        json={"message": "Hello"}
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    
    # 验证流式内容
    content = response.text
    
    # 验证包含 SSE 数据结构
    assert 'data: {"content":' in content
    
    # 验证包含结束标记
    assert "[DONE]" in content
