from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# 接收前端的请求数据
class ChatRequest(BaseModel):
    user_id: Optional[str] = None       # 用户id
    message: str                        # 用户发送的消息
    model_name: str = "deepseek-chat"   # 模型名称，默认值
    enable_search: bool = False         # 是否开启联网搜索
    enable_rag: bool = False            # 是否使用使用私有知识库
    file_ids: List[str] = []
    conversation_id: Optional[str] = None # 会话ID (第一次对话可能为空)
    parent_id: Optional[str] = None       # 父节点ID (用于树状对话)
    
    # ★★★ 新增：即时聊天文件 (支持多模态) ★★★
    # 格式示例: [{"name": "a.png", "type": "image", "base64": "...", "size": 1024}]
    files: List[Dict[str, Any]] = []

# 接收前端的文件数据


# 返回给前端的响应数据
class ChatResponse(BaseModel):
    content: str                        # AI 的回答内容
    source: str = "ai"                  # 来源标识 (ai / rag / search)

class SearchQuery(BaseModel):
    queries: List[str] = Field(description="生成的搜索关键词列表")
