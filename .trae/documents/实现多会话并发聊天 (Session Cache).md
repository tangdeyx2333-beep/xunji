# 多会话并发聊天支持计划

为了实现“在两个会话中同时与 AI 交流且互不干扰”，我们需要对前端的状态管理进行重构，引入 **会话缓存机制 (Session Cache)**。

## 核心原理

目前的障碍是前端只有一个全局的 `chatHistory` 和 `isSending` 状态。切换会话时，旧的状态会被丢弃或覆盖。
我们将建立一个 `sessionCache`，将每个会话的状态（消息记录、是否正在发送、上下文节点）独立存储。即使你切走了，后台的流式接收回调依然会更新缓存中的数据。当你切回来时，界面会直接从缓存渲染，无缝衔接。

## 实施步骤

### 1. 引入 SessionCache

在 `GeminiLayout.vue` 中创建一个响应式对象 `sessionCache`，用于存储所有已加载会话的状态：

```javascript
const sessionCache = reactive({
  // [conversationId]: {
  //   messages: [],       // 消息列表
  //   isSending: false,   // 该会话是否正在发送
  //   currentLeafId: null // 上下文节点
  // }
})
```

### 2. 重构 switchSession (切换会话)

* **切出前**：当前会话的状态天然保存在 `sessionCache` 中（因为我们将让 `chatHistory` 直接指向 Cache 中的数组）。

* **切入后**：

  * **检查缓存**：如果 `sessionCache[targetId]` 存在，直接将视图状态（`chatHistory`, `isSending` 等）指向缓存中的对象。这样你可以立刻看到之前的进度。

  * **未命中缓存**：调用 API 加载历史记录，加载完成后在 `sessionCache` 中创建新条目，并指向它。

### 3. 重构 sendMessage (发送消息)

* **发送锁隔离**：不再检查全局的 `isSending`，而是检查当前会话的 `sessionCache[id].isSending`。这允许你在会话 A 发送时，切换到会话 B 再点发送。

* **新会话处理**：

  * 当在“新会话”（无 ID）发送第一条消息时，我们会先在一个临时状态中处理。

  * 一旦收到后端返回的 `session_id`，立即将这个临时状态“转正”，存入 `sessionCache`，确保后续流式更新能正确归位。

### 4. 界面优化

* **侧边栏状态指示**：(可选) 在侧边栏的会话列表中，给正在生成回复的会话加一个“加载中”的小动画，让你知道哪些会话正在忙碌。

## 预期效果

1. 你可以在会话 A 提问，立刻切到会话 B 提问。
2. 两个会话的 AI 会并行回复（依赖浏览器的并发能力）。
3. 切回会话 A，你可以看到 AI 正在逐字输出，或者已经输出完成的内容，不会丢失任何进度。

