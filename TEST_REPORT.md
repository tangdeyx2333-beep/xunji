# TEST_REPORT

## 测试范围
- 附件 signed URL 接口：权限校验、过期时间上限
- 历史消息接口：附件元信息返回（不返回永久 URL）
- 聊天流式生成器：在流式链路内触发“附件保存结果”事件输出
- 附件落库服务：将上传结果写入 `message_attachments`

## 测试用例清单
- `tests/test_attachments_signed_url.py`
  - `test_signed_url_requires_owner`
    - 输入：当前用户请求不属于自己的 `attachment_id`
    - 预期：HTTP 403
  - `test_signed_url_expiry_clamp`
    - 输入：传入超大 `expires_seconds`
    - 预期：后端按 `SIGNED_URL_EXPIRES_SECONDS_MAX` 进行上限裁剪
- `tests/test_chat_attachments_and_history.py`
  - `test_chat_attachment_saved_after_ai`
    - 输入：构造会话/用户消息节点，运行聊天流式生成器并模拟附件保存结果
    - 预期：输出包含 `user_attachments_saved` 事件
  - `test_history_returns_attachment_metadata_no_url`
    - 输入：历史消息接口返回包含附件记录
    - 预期：attachments 中包含 `storage_key/storage_provider` 且不包含 `url`
- `tests/test_attachment_service.py`
  - `test_save_chat_attachments_creates_rows`
    - 输入：模拟 `object_storage.upload_bytes` 返回上传结果
    - 预期：写入 `message_attachments`，返回的 saved 列表与 DB 行一致

## 自检通过声明
- 已在本地执行 `python -m pytest -q`，全部测试通过。

