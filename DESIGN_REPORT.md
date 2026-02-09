# DESIGN_REPORT - 会话切换状态管理优化

## 1. 修改摘要
修复了在切换会话或开启新会话时，设置界面（嵌入式）和会话指令弹窗不会自动关闭的问题。

## 2. 架构设计思路
### 现状分析
- **组件结构**：`GeminiLayout.vue` 使用 `v-if="showSettings"` 控制设置界面，其与聊天主界面 (`.chat-container-wrapper`) 是互斥关系（`v-else`）。
- **状态变量**：
    - `showSettings`: 控制嵌入式设置面板。
    - `showConversationInstructions`: 控制会话指令弹窗。
    - `showChatTree`: 控制聊天树状图弹窗。
- **核心问题**：这些状态变量属于组件级响应式状态。在执行 `switchSession`（切换会话）或 `startNewChat`（开始新会话）逻辑时，并未重置这些状态，导致 UI 仍锁定在“设置模式”或弹窗遮挡状态。

### 优化方案
在所有涉及**会话上下文切换**的核心函数中，显式执行“UI 状态归位”操作：
- 重置 `showSettings.value = false`
- 重置 `showConversationInstructions.value = false`
- 重置 `showChatTree.value = false`

这种设计遵循了“状态机”的思想，确保进入新会话时，UI 处于一致的初始状态。

## 3. 环境变量配置指南
本项目不涉及新增环境变量。

## 4. 设计初衷 (Why)
- **低耦合**：将 UI 状态重置逻辑集中在会话切换函数中，避免了在每个 UI 组件内部监听会话变化，降低了逻辑复杂度。
- **高可用**：确保用户在任何状态下切换会话，都能立即看到聊天内容，提升了交互的流畅度。
