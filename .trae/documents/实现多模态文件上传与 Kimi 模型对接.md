# 多模态文件上传与 Kimi 对接实现计划

为了实现“上传文件（图片/视频/文档）给模型（主要是 Kimi 2.5）理解”的功能，我们需要对前后端进行改造。

## 核心挑战

1.  **消息格式差异**：
    *   **普通模型**：接收纯文本 `str`。
    *   **Kimi (OpenAI 兼容接口)**：接收 `List[Dict]`，即 `[{"type": "text", ...}, {"type": "image_url", ...}]`。
    *   **本地 RAG**：现有的文件上传逻辑是将文件转为向量库，而用户的需求是**直接将文件内容传给模型的上下文窗口**（Long Context），而非通过 RAG 检索。

2.  **Base64 编码**：前端需要将图片/视频转为 Base64 字符串发送给后端，后端再封装成 Kimi 需要的格式。

3.  **模型兼容性检查**：并非所有模型都支持多模态（如 `deepseek-chat` 暂不支持）。需要一个配置名单来决定是否启用多模态逻辑，否则回退到纯文本或报错。

## 实施步骤

### Phase 1: 后端改造 (Backend)

#### 1. 扩展 `ChatRequest` Schema
在 `app/schemas/chat.py` 中增加字段以支持 Base64 文件内容：
```python
class ChatRequest(BaseModel):
    # ... 原有字段 ...
    # 新增
    files: Optional[List[Dict[str, str]]] = None 
    # 格式示例: [{"type": "image", "base64": "...", "mime": "image/jpeg"}, {"type": "file", "content": "文本内容..."}]
```

#### 2. 修改 `ChatService` 构建 Prompt 逻辑
在 `app/services/chat_services.py` 中：
*   **判断模型能力**：创建一个 `MULTIMODAL_MODELS` 列表（如 `['kimi', 'moonshot-v1']`）。
*   **分支处理**：
    *   **Case A: 纯文本模型**：保持原有逻辑，如果是文件，尝试提取文本内容拼接到 Prompt 中。
    *   **Case B: 多模态模型 (Kimi)**：构建 `List[ContentPart]` 格式的消息。
        *   图片 -> `{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}`
        *   视频 -> Kimi 特有的 `video_url` 格式（注意：Kimi API 对视频通常需要上传到临时存储获取 URL，或者是 Base64，需确认文档。如果是 Base64，格式类似图片）。
        *   普通文件 -> 读取内容作为 `text` 部分。

#### 3. 增强 `ChatService.astream_chat_with_model`
修改调用 LangChain 的部分。由于 LangChain 的 `ChatOpenAI` 封装已经支持多模态（只要传入 list 格式的 content），我们需要确保传递给 `.invoke` 或 `.stream` 的 `input` 字典中的 `message` 是正确构造的对象列表，而不仅仅是字符串。

### Phase 2: 前端改造 (Frontend)

#### 1. 改造文件上传组件
*   目前前端的上传是“上传到知识库（RAG）”。
*   我们需要新增一种“上传到当前会话窗口”的逻辑。
*   **UI 变更**：输入框的📎按钮，点击后选择文件。
    *   **图片/视频**：读取为 Base64，在输入框上方显示缩略图预览。
    *   **文档**：读取文件名，准备作为文本发送。

#### 2. 发送逻辑 (`sendMessage`)
*   在 `sendMessage` 时，检查附件列表。
*   将附件转为 Base64（图片）或文本内容（小文件直接读内容），填入 `payload.files`。
*   调用 `chatStream` 发送。

### Phase 3: 数据库存储 (可选但推荐)

*   **Message 表**：目前的 `content` 是纯文本。
*   **方案**：如果包含多模态内容，`content` 字段可以存为一个 JSON 字符串，或者我们只存用户的文本指令，而将图片/文件作为附件关联（但这比较复杂）。
*   **简化方案**：对于历史记录回显，暂时只显示“[图片]”或“[文件]”的占位符，或者如果数据库支持，存入 JSON。考虑到工作量，**初步阶段建议只在内存中构建多模态 Prompt 发送给模型，数据库只存用户的文本 Query**（或者存 "User sent an image: [Base64...]"，但这会很大）。
*   **决策**：为了不炸库，数据库中 `content` 存 "[图片]" 文本，或者仅存用户输入的文字。实际发送给模型时，如果是新消息，带上图片；如果是历史记录，可能就不带图片了（除非模型支持多轮多模态历史，Kimi 是支持的）。

## 兼容性列表 (Config)

在 `app/core/config.py` 或 `model_manager.py` 中定义：
```python
SUPPORTED_MULTIMODAL_MODELS = ["kimi", "moonshot", "gemini", "gpt-4-vision", "gpt-4o"]
```

## 风险评估
*   **Token 消耗**：图片/视频 Base64 极大，可能导致 Token 消耗激增。
*   **延迟**：上传大文件 Base64 会增加 HTTP 请求体大小，导致延迟。

我们将优先实现 **Kimi 的图片和视频理解**，文档则作为纯文本处理。

