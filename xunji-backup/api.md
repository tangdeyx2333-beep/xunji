# 知微 (ZhiWei) RAG API 接口文档

## 1. 认证接口（Authentication）

### `/api/auth/register` (POST)
- **功能**: 用户注册
- **请求头**: `Content-Type: application/json`
- **请求体** ([UserCreate](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\schemas\auth.py#L4-L7)):
  ```json
  {
    "username": "string",
    "password": "string", 
    "email": "string"
  }
  ```

- **响应体** ([UserOut](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\schemas\auth.py#L25-L31)):
  ```json
  {
    "id": "string",
    "username": "string",
    "email": "string"
  }
  ```

- **HTTP状态码**:
  - 200: 注册成功
  - 400: 用户名已被注册

---

### `/api/auth/login` (POST)
- **功能**: 用户登录
- **请求头**: `Content-Type: application/json`
- **请求体** ([UserLogin](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\schemas\auth.py#L11-L13)):
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```

- **响应体** ([Token](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\schemas\auth.py#L17-L21)):
  ```json
  {
    "access_token": "string",
    "token_type": "string",
    "user_id": "string",
    "username": "string"
  }
  ```

- **HTTP状态码**:
  - 200: 登录成功
  - 401: 用户名或密码错误

---

## 2. 聊天接口（Chat）

### `/api/chat` (POST)
- **功能**: 与AI模型进行聊天
- **请求头**: 
  - `Content-Type: application/json`
  - `Authorization: Bearer {token}`
- **请求体** (`ChatRequest`):
  ```json
  {
    "user_id": "string",
    "message": "string",
    "model_name": "string",
    "enable_search": false,
    "enable_rag": false,
    "file_ids": [],
    "conversation_id": "string"
  }
  ```

- **响应体** (`ChatResponse`):
  ```json
  {
    "content": "string",
    "source": "ai"
  }
  ```

- **HTTP状态码**:
  - 200: 成功
  - 401: 未授权

---

## 3. 文件上传接口（Upload/File）

### `/api/upload` (POST)
- **功能**: 上传文件到知识库
- **请求头**: `Authorization: Bearer {token}`
- **请求参数**:
  - `file`: 文件上传 (form-data)
- **响应体** (`UploadResponse`):
  ```json
  {
    "filename": "string",
    "file_id": "string",
    "message": "string"
  }
  ```

- **HTTP状态码**:
  - 200: 上传成功
  - 400: 仅支持 PDF, TXT 或 MD 文件
  - 401: 未授权
  - 500: 文件处理失败

---

### `/api/files` (GET)
- **功能**: 获取当前用户的文件列表
- **请求头**: `Authorization: Bearer {token}`
- **响应体** (`FileDTO[]`):
  ```json
  [
    {
      "id": "string",
      "filename": "string",
      "created_at": "2026-01-30T00:00:00",
      "file_size": 0
    }
  ]
  ```

- **HTTP状态码**:
  - 200: 成功
  - 401: 未授权

---

### `/api/files/{file_id}` (DELETE)
- **功能**: 删除指定文件
- **请求头**: `Authorization: Bearer {token}`
- **路径参数**:
  - [file_id](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\api\endpoints\upload.py#L29-L29): 文件唯一标识符 (string)
- **响应体**:
  ```json
  {
    "message": "文件已移除"
  }
  ```

- **HTTP状态码**:
  - 200: 文件已移除
  - 401: 未授权
  - 404: 文件不存在

---

## 4. 检索接口（Retrieval/Debug）

### `/api/debug/db_status` (GET)
- **功能**: 获取数据库状态（调试用）
- **请求头**: `Authorization: Bearer {token}`
- **响应体**: 数据库统计信息
- **HTTP状态码**:
  - 200: 成功
  - 401: 未授权

---

### `/api/retrieval/search` (POST)
- **功能**: 向量检索搜索
- **请求头**: 
  - `Content-Type: application/json`
  - `Authorization: Bearer {token}`
- **请求体** ([SearchRequest](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\api\endpoints\retrieval.py#L11-L14)):
  ```json
  {
    "query": "string",
    "top_k": 3,
    "file_ids": []
  }
  ```

- **响应体**:
  ```json
  {
    "message": "检索成功",
    "count": 0,
    "results": []
  }
  ```

- **HTTP状态码**:
  - 200: 成功
  - 401: 未授权
  - 500: 内部服务器错误

---

## 5. 历史记录接口（History/Session）

### `/api/conversations` (GET)
- **功能**: 获取会话列表
- **请求头**: `Authorization: Bearer {token}`
- **查询参数**:
  - `limit`: 返回数量限制 (int, 默认20)
- **响应体** (`ConversationDTO[]`):
  ```json
  [
    {
      "id": "string",
      "title": "string",
      "updated_at": "2026-01-30T00:00:00",
      "created_at": "2026-01-30T00:00:00"
    }
  ]
  ```

- **HTTP状态码**:
  - 200: 成功
  - 401: 未授权

---

### `/api/conversations/{conversation_id}/messages` (GET)
- **功能**: 获取指定会话的消息记录
- **请求头**: `Authorization: Bearer {token}`
- **路径参数**:
  - [conversation_id](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\schemas\chat.py#L11-L11): 会话唯一标识符 (string)
- **响应体** (`MessageDTO[]`):
  ```json
  [
    {
      "id": "string",
      "role": "string",
      "content": "string",
      "created_at": "2026-01-30T00:00:00",
      "type": "string"
    }
  ]
  ```

- **HTTP状态码**:
  - 200: 成功
  - 401: 未授权
  - 404: 会话不存在

---

### `/api/conversations/{conversation_id}` (DELETE)
- **功能**: 删除指定会话（软删除）
- **请求头**: `Authorization: Bearer {token}`
- **路径参数**:
  - [conversation_id](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\schemas\chat.py#L11-L11): 会话唯一标识符 (string)
- **响应体**:
  ```json
  {
    "message": "会话已删除",
    "conversation_id": "string"
  }
  ```

- **HTTP状态码**:
  - 200: 成功
  - 401: 未授权
  - 404: 会话不存在

---

## 6. 主页接口

### [/](file://F:\aaa_desktop_file\python-study\rag_search_ai\app\api\deps.py) (GET)
- **功能**: 根路径测试
- **响应体**:
  ```json
  {
    "message": "知微后端服务已启动 🚀"
  }
  ```

- **HTTP状态码**:
  - 200: 成功

---

## 项目特点：
1. **基于FastAPI**: 使用现代Python框架，支持异步操作
2. **RAG系统**: 支持知识库检索增强功能
3. **用户认证**: 包含完整的用户注册、登录和JWT认证机制
4. **文件管理**: 支持PDF、TXT、MD等格式文件上传
5. **会话管理**: 支持多轮对话和历史记录管理
6. **数据库**: 使用SQLAlchemy ORM，支持SQLite/MySQL等数据库
7. **向量数据库**: 使用ChromaDB存储文档向量用于检索
8. **CORS配置**: 支持前端跨域访问

该项目是一个完整的RAG系统，支持用户认证、文件上传、知识库检索、多轮对话等功能。所有需要保护的接口都需要通过JWT进行身份验证。