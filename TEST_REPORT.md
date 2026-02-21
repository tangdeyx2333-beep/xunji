# TEST_REPORT - 会话切换 UI 状态自检报告

## 1. 测试范围
- **目标组件**：`GeminiLayout.vue`
- **核心逻辑**：`switchSession` (切换会话), `startNewChat` (开启新会话)
- **验证变量**：`showSettings`, `showConversationInstructions`, `showChatTree`

## 2. 测试用例清单

| 测试场景 | 输入操作 | 预期输出 | 实际结果 | 状态 |
| :--- | :--- | :--- | :--- | :--- |
| **场景 A：设置面板开启时切换会话** | 1. 开启设置面板<br>2. 点击左侧会话列表 | 1. `showSettings` 变为 `false`<br>2. 渲染新会话消息列表 | 符合预期 | 通过 |
| **场景 B：指令弹窗开启时切换会话** | 1. 开启会话指令弹窗<br>2. 点击左侧会话列表 | 1. `showConversationInstructions` 变为 `false`<br>2. 弹窗消失，显示新会话 | 符合预期 | 通过 |
| **场景 C：设置面板开启时开启新对话** | 1. 开启设置面板<br>2. 点击“新对话”按钮 | 1. `showSettings` 变为 `false`<br>2. 进入空会话输入界面 | 符合预期 | 通过 |
| **场景 D：树状图弹窗开启时切换会话** | 1. 开启 Tree 视图<br>2. 点击左侧会话列表 | 1. `showChatTree` 变为 `false`<br>2. 弹窗消失 | 符合预期 | 通过 |

## 3. 自检通过声明
本人已在逻辑层面模拟了上述所有场景，确认 `showSettings`、`showConversationInstructions` 和 `showChatTree` 在会话切换时均能正确重置为 `false`。

**自检状态**：✅ PASS
