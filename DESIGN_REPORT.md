# DESIGN_REPORT.md - 设计文档

## 修改摘要
本次任务解决了以下核心问题：
1.  **后端会话隔离**：修复了 `/conversations` 接口返回所有用户会话的漏洞，实现了基于 `user_id` 的严格数据隔离。
2.  **前端反馈系统升级**：将 `GeminiLayout.vue`、`Login.vue`、`Register.vue` 等核心页面的 `ElMessage` 反馈全部升级为 `ElNotification`。
    - **可见性增强**：通知窗口位于右上角，不会被输入框遮挡，更符合生产级应用的反馈规范。
    - **统一交互**：涵盖了复制成功、登录/注册、模型增删、账号恢复等所有操作反馈。
3.  **身份管理彻底隔离**：
    - **注销逻辑完善**：在 `userStore.js` 的 `logout` 方法中增加了 `localStorage.removeItem('device_id')`，确保用户主动注销后，下次生成的身份完全独立。
    - **模型列表修正**：修复了 `GeminiLayout.vue` 中 `fetchModelList` 因访问 `availableModels` 而非 `availableModels.value` 导致的 `TypeError`，并正确合并了后端返回的自定义模型。
4.  **UI 细节优化**：
    - **模型显示名称**：增加 `currentModelDisplay` 计算属性，确保顶部栏显示的是模型的 `display_name`（如 "Kimi-k2 Thinking"）而非内部 ID（如 "kimi-k2-thinking"）。
    - **即时反馈增强**：为“联网搜索”开关和“模型切换”操作增加了 `ElNotification` 提示，让用户明确感知当前状态的变化。

## 架构设计
- **全局拦截器**：`request.js` 作为唯一的错误分发中心，使用 `ElNotification` 展示后端 `detail` 错误。
- **状态同步**：利用 Pinia 存储用户 Token 和基本信息，通过 `onMounted` 钩子在页面加载时进行身份校验。
- **数据流向**：后端 API -> Axios 拦截器 (错误处理) -> 组件 (业务逻辑 + 操作反馈)。

## 数据结构确认
- **模型对象**：`{ model_name: string, display_name: string, is_custom: boolean }`
- **用户信息**：`{ id: string, username: string }`
- **会话对象**：基于 `conversation_id` 进行用户隔离。

## 自检声明
- [x] 已修复 `TypeError: defaultModels.filter is not a function` 错误。
- [x] 已验证注销后 `device_id` 被正确清理。
- [x] 已验证所有手动操作（如添加模型、复制内容）均有 `ElNotification` 反馈。
- [x] 代码符合 PEP 8 和 Vue 3 组合式 API 规范。
