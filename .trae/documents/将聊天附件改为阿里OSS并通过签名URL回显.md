## 目标
- 聊天输入框附件（尤其图片）在**拿到 AI 回复后**再上传到**阿里云 OSS**，并把 OSS 返回的 `object_key/filename` 与用户消息关联落库。
- 前端历史回显时不直接拿永久 URL；当检测到附件记录后，向后端请求**带过期时间 + 权限校验**的 signed URL，再用该 URL 拉取文件。

## 现状评估（基于代码检索）
- 当前代码只集成了腾讯 COS（并且把 `url` 直接落库/直接回显），没有阿里 OSS 依赖与 signed-url 接口：
  - COS 封装：[oss_service.py](file:///f:/aaa_desktop_file/xunji/xunji-backup/app/services/oss_service.py)
  - 聊天保存 COS 附件并把 `url` 回传：[chat.py](file:///f:/aaa_desktop_file/xunji/xunji-backup/app/api/endpoints/chat.py)
  - 历史接口直接回传 `url`：[history.py](file:///f:/aaa_desktop_file/xunji/xunji-backup/app/api/endpoints/history.py)
- 阿里 OSS Python SDK 计划采用 `oss2`，支持 `bucket.put_object` 上传与 `bucket.sign_url('GET', key, expires, ...)` 生成临时下载链接（官方示例支持设定有效期，V4 presigned URL 最大 7 天）
  - 参考：Alibaba OSS Python SDK（oss2）与 presigned URL 文档。

## 设计方案

### 1) 后端：对象存储抽象（COS -> 阿里 OSS）
- 新增 `AliOssService`（基于 `oss2`），实现：
  - `upload_bytes(...) -> {storage_key, filename, mime, size}`
  - `sign_get_url(storage_key, expires_seconds) -> signed_url`
- 保留现有 `OssService(COS)` 但改为可插拔（或直接切换默认 provider 到 aliyun），通过配置项 `OBJECT_STORAGE_PROVIDER=aliyun|cos|disabled` 选择。
- 关键：DB 不再持久化 `url`（或将其置空），改存 `storage_provider + storage_key + filename`，URL 由签名接口实时生成。

### 2) 后端：DB 与 DTO 调整
- 使用现有 `message_attachments` 表（已存在）作为统一附件表，但字段策略调整：
  - `storage_key`（必填）
  - `storage_provider`（必填：aliyun/cos）
  - `url` 字段不再作为强依赖（可保留但不写入/置空），避免“过期 URL”落库。
- 历史接口 DTO（`/api/conversations/{id}/messages`、`/api/tree/path/{node_id}`）：
  - 返回附件的 `id/filename/mime/size/storage_provider/storage_key`
  - 不返回可直接访问的 URL（或返回 `url: null`），前端需要另取签名 URL。

### 3) 后端：签名 URL 获取接口（带权限与过期时间）
- 新增端点：`GET /api/attachments/{attachment_id}/signed-url`
  - Auth：必须登录
  - ACL：校验 `attachment.user_id == current_user.id`（或同会话归属）
  - Expires：默认取 `OSS_SIGNED_URL_EXPIRES_SECONDS`（配置），可允许 query 覆盖但要限制最大值（<= 7 天）
  - 返回：`{url, expires_at}`
- 签名 URL 生成使用 `oss2.Bucket.sign_url('GET', object_key, expires, slash_safe=True)`（V4 签名与最大有效期 7 天约束按阿里官方文档）。

### 4) 后端：聊天流程调整（先 AI 后上传）
- 现有流程是“保存用户消息 -> 上传附件 -> 流式输出 AI -> 保存 AI 消息”。
- 按你的新要求改为：
  1. 保存用户消息（不含附件 URL，仅保留原文/占位）
  2. 流式输出 AI，流结束后保存 AI 消息与树节点
  3. **流结束后**上传用户本次请求携带的附件到阿里 OSS
  4. 将附件写入 `message_attachments`（关联到用户消息）
  5. 再通过 SSE 发送一个 meta 包：`{user_attachments_saved: [{id, filename, mime, size, storage_key, storage_provider}]}`，让前端即时把“本条用户消息”补齐附件信息（无需刷新）。

### 5) 前端：按需拉取 signed URL 并回显
- 发送阶段：继续本地预览 base64（用户体验不变）。
- 历史回显阶段：
  - 若消息 `attachments` 里存在 `storage_key` 但无 `url`，前端调用新接口获取 signed URL
  - 缓存策略：按 `attachment_id` 缓存到过期时间（避免频繁请求）
  - 展示：
    - image：`<img :src="signedUrl">`
    - video：`<video :src="signedUrl" controls>`
    - 其他：下载链接

## 配置与模板（强制注释块）
- 更新 `xunji-backup/.env.example` 与 `xunji-frontend/.env.example`：
  - 每个变量上方增加注释块，包含：
    - [必须/可选]
    - [配置效果]
    - [格式/默认值]
  - 新增后端变量（示例）：
    - `OBJECT_STORAGE_PROVIDER=aliyun`
    - `ALIYUN_OSS_ACCESS_KEY_ID`、`ALIYUN_OSS_ACCESS_KEY_SECRET`、`ALIYUN_OSS_ENDPOINT`、`ALIYUN_OSS_BUCKET`
    - `ALIYUN_OSS_PREFIX`（可选）
    - `OSS_SIGNED_URL_EXPIRES_SECONDS`（默认/最大限制说明）

## 测试（先测后交付）
使用 `pytest`（若仓库未配置则补最小 pytest 配置与依赖）新增：
1. `test_signed_url_requires_owner`：非本人请求附件 signed url 返回 403。
2. `test_signed_url_expiry_clamp`：expires 超过上限会被 clamp。
3. `test_chat_attachment_saved_after_ai`：模拟流式返回后才调用 `upload_bytes`，并在 DB 生成 `message_attachments` 记录。
4. `test_history_returns_attachment_metadata_no_url`：历史接口返回 attachments 元信息但不包含永久 url。

## 交付物
- 后端源代码（Ali OSS service + signed url endpoint + chat 流程改造 + DTO 调整）
- 测试代码（pytest）
- 更新后的配置模板（带注释块）
- 更新 [DESIGN_REPORT.md](file:///f:/aaa_desktop_file/xunji/DESIGN_REPORT.md)
- 新增 `TEST_REPORT.md`

如果你确认这个方案，我将开始按上述步骤落地实现与测试。