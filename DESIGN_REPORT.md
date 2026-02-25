# DESIGN_REPORT.md - 设计文档

## 修改摘要
本次任务解决了以下核心问题：
1.  **后端会话隔离**：修复了 `/conversations` 接口返回所有用户会话的漏洞，实现了基于 `user_id` 的严格数据隔离。
2.  **前端错误处理优化**：清理了 `GeminiLayout.vue` 中冗余的 `ElMessage.error` 调用，统一由 `request.js` 拦截器根据后端返回的 `detail` 字段进行精准报错。
3.  **身份重置机制**：优化了注销逻辑，确保注销时清除 `token`、用户信息及设备指纹（Fingerprint），防止刷新后身份恢复。

## 架构设计
- **后端隔离**：通过 FastAPI 的 `Depends(get_current_user)` 依赖注入获取当前用户，并在所有历史记录相关接口中增加 `filter(Conversation.user_id == current_user.id)` 约束。
- **前端统一报错**：利用 Axios 响应拦截器，捕获非 2xx 响应，提取 `error.response.data.detail` 并通过 `ElMessage.error` 展示。在组件内部仅保留 `console.error` 用于调试，避免双重弹窗。
- **状态管理**：在 `userStore.logout()` 中增加对 `localStorage` 键值的清理逻辑。

## 数据结构确认
代码处理逻辑严格遵循以下字段，未添加任何额外字段：
- **Conversation**: `id`, `user_id`, `is_deleted`, `updated_at` 等。
- **User**: `id`, `username` 等。
- **API Response**: `detail` 字段用于传递错误信息。
