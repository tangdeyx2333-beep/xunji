## 目标
- 为“每个会话（conversation）”增加一组可管理的 AI 指令（数组）。
- 发起聊天请求时，将“会话指令”拼接到 system prompt 中（与现有“全局用户指令”并存）。

## 后端改造
### 1) 数据库表
- 新增表 `conversation_ai_instructions`（推荐独立表，避免与全局指令混淆）：
  - `id`、`conversation_id`(FK conversations.id)、`user_id`(冗余用于隔离/索引)、`content`、`sort_order`、`created_at`、`updated_at`、`is_deleted`
- 索引建议：`(conversation_id, sort_order)`、`(user_id, conversation_id)`。
- 保持现有 `ai_instructions` 作为“全局指令”。

### 2) API 设计
- 新增会话维度指令 CRUD：
  - `GET /api/conversations/{conversation_id}/instructions`
  - `POST /api/conversations/{conversation_id}/instructions`
  - `PUT /api/conversations/{conversation_id}/instructions/{instruction_id}`
  - `DELETE /api/conversations/{conversation_id}/instructions/{instruction_id}`（软删）
- 权限：每个接口都校验 `conversation.user_id == current_user.id`，并且指令操作强制 `conversation_id` 匹配。

### 3) 注入 system prompt
- 在 `ChatService.astream_chat_with_model` 中：
  - 继续读取“全局指令”（现有 `_get_user_instructions`）。
  - 新增 `_get_conversation_instructions(db, conversation_id, user_id)`。
  - 注入顺序建议：
    - 先全局指令（全局规则）
    - 再会话指令（更贴近当前对话的规则，优先级更高）
  - 输出格式示例：
    - `全局指令：\n1....\n\n会话指令：\n1....`
- 多模态与非多模态两条链路都保持一致拼接。

### 4) 约束（可选但推荐）
- 单条指令最大长度（默认 500）
- 每会话最大条数（默认 20）
- 超限返回 400

## 前端改造
### 1) API 封装
- 在 `src/api/chat.js` 增加会话指令 API：
  - `getConversationInstructions(conversationId)`
  - `createConversationInstruction(conversationId, data)`
  - `updateConversationInstruction(conversationId, instructionId, data)`
  - `deleteConversationInstruction(conversationId, instructionId)`

### 2) UI 入口与交互
- 在 `GeminiLayout.vue`：
  - 为“当前会话”在顶部 header 增加「会话指令」按钮（没有会话ID时禁用或提示先发一条消息生成会话）。
  - 弹出 `el-dialog`/`el-drawer`：
    - textarea + 添加按钮
    - 列表表格：内容 + 上移/下移（改 sort_order）+ 删除
  - 打开弹窗时自动拉取该会话的指令。

## 测试（后端）
- 新增 pytest：
  - 会话指令 CRUD 权限隔离（不同用户/不同 conversation_id 不能互操作）。
  - prompt 注入：构造带 `conversation_id` 的请求，断言 system prompt 同时包含全局与会话指令，且顺序正确。

## 验证方式
- 运行后端测试用例。
- 前端 `npm run build` 通过。
- 手动验证：同一用户不同会话指令互不影响；新会话首次发送后可配置会话指令并生效。

如果你确认这个方案，我将开始按以上步骤落地实现（后端表+接口+注入、前端入口+管理界面、测试用例与构建验证）。