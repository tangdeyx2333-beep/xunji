## 需求
- 在“设置”里新增一项：AI 指令（数组）。
- 指令需要持久化到数据库（新增一张表）。
- 每次发起对 AI 的请求时，把这些指令拼接进系统提示词（system prompt）中。

## 后端改动
### 1) 新增表（SQLAlchemy）
- 在 [sql_models.py](file:///f:/aaa_desktop_file/xunji/xunji-backup/app/models/sql_models.py) 新增 `AiInstruction`（表名建议 `ai_instructions`）。
- 字段建议：
  - `id` (String, pk)
  - `user_id` (FK users.id, 必填，按用户隔离)
  - `content` (Text，单条指令)
  - `sort_order` (Integer，保证“数组顺序”) 
  - `created_at`/`updated_at` (DateTime)
  - `is_deleted` (Boolean，软删除可选；也可硬删，和 models 一致)
- 说明：项目启动会 `create_all`，新增表会自动创建，不需要手动迁移脚本（已有 DB 也能补表）。

### 2) 新增指令管理 API（FastAPI）
- 新建 `app/api/endpoints/instructions.py`（风格参考 [models.py](file:///f:/aaa_desktop_file/xunji/xunji-backup/app/api/endpoints/models.py)）：
  - `GET /api/instructions`：返回当前用户的指令列表（按 `sort_order asc, created_at asc`）。
  - `POST /api/instructions`：新增一条指令（`content` 必填），`sort_order` 默认追加到末尾。
  - `PUT /api/instructions/{id}`：更新指令内容/顺序（可选但推荐，便于前端拖拽/上下移动）。
  - `DELETE /api/instructions/{id}`：删除指令（硬删或软删，建议与 models 一致用硬删）。
- 在 [main.py](file:///f:/aaa_desktop_file/xunji/xunji-backup/app/main.py#L30-L38) 注册该 router。

### 3) 注入到 system prompt
- 在 `ChatService.astream_chat_with_model` 内（[chat_services.py](file:///f:/aaa_desktop_file/xunji/xunji-backup/app/services/chat_services.py#L272-L402)）：
  - 使用当前的 `db` + `request.user_id` 读取该用户的指令数组。
  - 组装成一段稳定格式的文本（例如：
    - `额外指令：\n1. ...\n2. ...`）
  - 多模态分支：拼进 `sys_msg_content`（system message）。
  - 非多模态分支：把 `qa_prompt` 的 system 模板扩展为包含 `{extra_instructions}` 占位符，并在 `chain.astream({...})` 传入该字段。

## 前端改动
### 1) API 封装
- 在 [chat.js](file:///f:/aaa_desktop_file/xunji/xunji-frontend/src/api/chat.js) 增加：
  - `getInstructions()` → `GET /api/instructions`
  - `createInstruction(data)` → `POST /api/instructions`
  - `updateInstruction(id, data)` → `PUT /api/instructions/{id}`
  - `deleteInstruction(id)` → `DELETE /api/instructions/{id}`

### 2) 设置页 UI（GeminiLayout.vue）
- 在设置弹窗 `<el-tabs>` 中新增一个 tab：`AI 指令`。
- UI 形态（尽量贴合现有模型管理风格）：
  - 顶部：输入框/textarea + “添加”按钮。
  - 列表：表格展示指令内容。
  - 操作：删除；可选增加“上移/下移”来修改 `sort_order`（对应调用 update）。
- 这些指令不需要在聊天消息区渲染，只影响模型侧 system prompt。

## 测试计划
- 后端 pytest：
  - CRUD：创建/查询/更新/删除指令（需校验 user 隔离）。
  - prompt 注入：用 FakeModel 截获传入 messages，断言 SystemMessage 含“额外指令”文本（覆盖多模态与非多模态）。
- 运行 `python -m pytest -q` 确保全绿。

## 兼容性与约束
- 为防止 prompt 过长：可在后端限制单条指令长度与最大条数（例如最多 20 条，每条 500 字），超出返回 400。
- 若用户未配置任何指令：系统提示词不额外拼接任何内容。